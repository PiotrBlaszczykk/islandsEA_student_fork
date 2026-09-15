"""Run one named benchmark through main_codebase's existing Ray island model.

Use --dry-run to validate without starting Ray. Submit run_ares.sh from the
repository root for SLURM; --ray-address local is an explicit local smoke mode.
"""
import argparse
import contextlib
from datetime import datetime, timezone
import importlib
import importlib.metadata
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import shutil
import socket
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT / "islands_desync"
sys.path.insert(0, str(PACKAGE_ROOT))

from islands_desync.islands.topologies.study import ISLANDS, TOPOLOGIES, validate_study
from islands_desync.islands.topologies.fixed_graph import graph_parameters
ACCEPTANCE = {"plain", "better", "newer", "older", "oldest", "stochastic", "rejectTooOld", "window"}


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--problem", required=True)
    p.add_argument("--dimension", type=int, required=True)
    p.add_argument("--islands", type=int, default=ISLANDS)
    p.add_argument("--diagnostic", action="store_true", help="Explicitly allow small smoke runs outside the 144-island study")
    p.add_argument("--evaluations", type=int, default=8000)
    p.add_argument("--population", type=int, default=16)
    p.add_argument("--offspring", type=int, default=4)
    p.add_argument("--migrants", type=int, default=5)
    p.add_argument("--interval", type=int, default=5)
    p.add_argument("--topology", choices=TOPOLOGIES, default="complete")
    p.add_argument("--torus-rows", type=int)
    p.add_argument("--torus-columns", type=int)
    p.add_argument("--strategy", choices=("best", "random", "maxDistance", "worst"), default="random")
    p.add_argument("--acceptance", default="plain")
    p.add_argument("--repeat", type=int, default=1)
    p.add_argument("--seed", type=int, default=20260912)
    p.add_argument("--ray-address", default="auto")
    p.add_argument("--local-cpus", type=int, default=6)
    p.add_argument("--ray-temp-dir")
    p.add_argument("--startup-timeout", type=float, default=120)
    p.add_argument("--actor-startup-timeout", type=float, default=300)
    p.add_argument("--result-pointer", help="Write final run/audit paths and status to this JSON file")
    p.add_argument(
        "--output-root",
        help="Override the raw results root (default: ISLANDS_RUN_OUTPUT_ROOT or $SCRATCH/islandsEA/results/runs)",
    )
    p.add_argument(
        "--audit-root",
        help="Override the compact audit root (default: ISLANDS_AUDIT_ROOT or $SCRATCH/islandsEA/results/audit)",
    )
    p.add_argument("--dry-run", action="store_true")
    return p


def torus_shape(args):
    """Return explicit rows/columns while preserving the historical 12-column default."""
    supplied = (args.torus_rows is not None, args.torus_columns is not None)
    if args.topology != "torus":
        if any(supplied):
            raise ValueError("--torus-rows/--torus-columns are valid only with --topology torus")
        return None
    if supplied[0] != supplied[1]:
        raise ValueError("Specify both --torus-rows and --torus-columns")
    if all(supplied):
        if args.torus_rows < 2 or args.torus_columns < 2:
            raise ValueError("Torus rows and columns must both be at least 2")
        if args.torus_rows * args.torus_columns != args.islands:
            raise ValueError("Torus rows * columns must equal the requested island count")
        return {"rows": args.torus_rows, "columns": args.torus_columns, "mode": "explicit"}
    if args.islands < 24 or args.islands % 12:
        raise ValueError(
            "The historical torus requires islands >= 24 and divisible by 12; "
            "otherwise provide an explicitly approved --torus-rows/--torus-columns shape"
        )
    return {"rows": args.islands // 12, "columns": 12, "mode": "historical-default"}


def selected_topology_parameters(args):
    shape = torus_shape(args)
    if args.topology in ("er4", "ws3", "ba"):
        return graph_parameters(args.topology)
    return shape


def storage_paths(args):
    storage_root = os.environ.get("ISLANDS_STORAGE_ROOT")
    fallback = False
    if not storage_root:
        storage_base = os.environ.get("SCRATCH") or os.environ.get("HOME")
        fallback = not bool(os.environ.get("SCRATCH"))
        storage_root = str(Path(storage_base) / "islandsEA") if storage_base else "islandsEA"
    results_root = os.environ.get(
        "ISLANDS_RESULTS_ROOT", str(Path(storage_root) / "results")
    )
    log_root = os.environ.get("ISLANDS_LOG_ROOT", str(Path(storage_root) / "logs"))
    paths = {
        "ISLANDS_STORAGE_ROOT": storage_root,
        "ISLANDS_RESULTS_ROOT": results_root,
        "ISLANDS_LOG_ROOT": log_root,
        "ISLANDS_CHECKPOINT_ROOT": os.environ.get(
            "ISLANDS_CHECKPOINT_ROOT", str(Path(storage_root) / "checkpoints")
        ),
        "ISLANDS_TMP_ROOT": os.environ.get(
            "ISLANDS_TMP_ROOT", str(Path(storage_root) / "tmp")
        ),
        "ISLANDS_RUN_OUTPUT_ROOT": args.output_root
        or os.environ.get("ISLANDS_RUN_OUTPUT_ROOT", str(Path(results_root) / "runs")),
        "ISLANDS_AUDIT_ROOT": args.audit_root
        or os.environ.get("ISLANDS_AUDIT_ROOT", str(Path(results_root) / "audit")),
        "ISLANDS_ARTIFACT_ROOT": os.environ.get(
            "ISLANDS_ARTIFACT_ROOT", str(Path(results_root) / "pilot_runs")
        ),
        "ISLANDS_SLURM_LOG_DIR": os.environ.get(
            "ISLANDS_SLURM_LOG_DIR", str(Path(log_root) / "slurm")
        ),
        "ISLANDS_RAY_FAILURE_ROOT": os.environ.get(
            "ISLANDS_RAY_FAILURE_ROOT", str(Path(log_root) / "ray_failures")
        ),
        "ISLANDS_STORAGE_FALLBACK": os.environ.get(
            "ISLANDS_STORAGE_FALLBACK", "1" if fallback else "0"
        ),
    }
    for key, value in tuple(paths.items()):
        if key != "ISLANDS_STORAGE_FALLBACK":
            paths[key] = str(Path(value).expanduser().resolve())
    return paths


def environment(args):
    from islands_desync.geneticAlgorithm.utils.matplotlib_setup import default_mpl_config_dir

    paths = storage_paths(args)
    return {
        **paths,
        "ISLANDS_CONFIG": str(Path(os.environ.get("ISLANDS_CONFIG", str(PACKAGE_ROOT / "islands_desync/geneticAlgorithm/algorithm/configurations/algorithm_configuration.json"))).resolve()),
        "ISLANDS_PROBLEM": args.problem.strip().lower(),
        "ISLANDS_NUMBER_OF_VARIABLES": str(args.dimension),
        "ISLANDS_NUMBER_OF_EVALUATIONS": str(args.evaluations),
        "ISLANDS_POPULATION_SIZE": str(args.population),
        "ISLANDS_OFFSPRING_POPULATION_SIZE": str(args.offspring),
        "ISLANDS_SEED": str(args.seed + (args.repeat - 1) * 1000000),
        "ISLANDS_EFFECT_HORIZON_STEPS": os.environ.get(
            "ISLANDS_EFFECT_HORIZON_STEPS", "25"
        ),
        "ISLANDS_DELIVERY_TIMEOUT_SECONDS": os.environ.get(
            "ISLANDS_DELIVERY_TIMEOUT_SECONDS", "300"
        ),
        "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1", "MPLBACKEND": "Agg",
        "MPLCONFIGDIR": os.environ.get("MPLCONFIGDIR", str(default_mpl_config_dir())),
        "TMPDIR": os.environ.get("TMPDIR", paths["ISLANDS_TMP_ROOT"]),
        "XDG_CACHE_HOME": os.environ.get(
            "XDG_CACHE_HOME", str(Path(paths["ISLANDS_TMP_ROOT"]) / "xdg-cache")
        ),
        "RAY_TMPDIR": os.environ.get(
            "RAY_TMPDIR", str(Path(paths["ISLANDS_TMP_ROOT"]) / "ray")
        ),
        "PYTHONPATH": str(PACKAGE_ROOT) + os.pathsep + os.environ.get("PYTHONPATH", ""),
    }


def validate(args):
    validate_study(args.islands, args.topology, args.diagnostic)
    from islands_desync.geneticAlgorithm.run_hpc.benchmark_configuration import create_problem, load_configuration
    if args.islands < 1 or args.repeat < 1 or args.seed < 0 or args.interval < 1:
        raise ValueError("islands/repeat/interval must be positive and seed nonnegative")
    if not 1 <= args.migrants <= args.population:
        raise ValueError("migrants must be between 1 and population size")
    if args.startup_timeout <= 0 or args.actor_startup_timeout <= 0 or args.local_cpus < 1:
        raise ValueError("startup-timeout, actor-startup-timeout and local-cpus must be positive")
    if int(os.environ.get("ISLANDS_EFFECT_HORIZON_STEPS", "25")) < 0:
        raise ValueError("ISLANDS_EFFECT_HORIZON_STEPS must be nonnegative")
    if float(os.environ.get("ISLANDS_DELIVERY_TIMEOUT_SECONDS", "300")) <= 0:
        raise ValueError("ISLANDS_DELIVERY_TIMEOUT_SECONDS must be positive")
    acceptance = args.acceptance.removeprefix("dup_").split(":", 1)
    if acceptance[0] not in ACCEPTANCE:
        raise ValueError("Unknown acceptance strategy")
    if len(acceptance) == 2:
        int(acceptance[1])
    shape = torus_shape(args)
    configuration = load_configuration()
    problem = create_problem(configuration["problem"], configuration["number_of_variables"])
    name = TOPOLOGIES[args.topology]
    cls = getattr(importlib.import_module("islands_desync.islands.topologies." + name), name)
    with contextlib.redirect_stdout(io.StringIO()):
        topology = cls(args.islands, lambda i: i)
        try:
            adjacency = (
                topology.create(shape["columns"], shape["rows"])
                if shape is not None
                else topology.create()
            )
        except (KeyError, IndexError) as error:
            raise ValueError(f"Topology {args.topology} does not support {args.islands} islands in its existing graph") from error
    if set(adjacency) != set(range(args.islands)):
        raise ValueError("Topology does not define every requested island")
    for source, targets in adjacency.items():
        if any(not isinstance(t, int) or not 0 <= t < args.islands for t in targets):
            raise ValueError(f"Topology {args.topology} has out-of-range neighbours for island {source}; its hardcoded graph may use another island count")
        if args.islands > 1 and not targets:
            raise ValueError(f"Island {source} has no destination for migration")
    return configuration, problem, cls, adjacency


def node_probe(name, dimension):
    # Executed on each allocated Ray node before the timed experiment.
    from islands_desync.geneticAlgorithm.run_hpc.benchmark_configuration import create_problem, load_configuration, runtime_sha256
    from islands_desync.geneticAlgorithm.utils.benchmarks_refined.provenance import implementation_sha256
    problem = create_problem(name, dimension)
    solution = problem.create_solution()
    problem.evaluate(solution)
    cwd = Path.cwd().resolve()
    required_runtime_path = cwd / "islands_desync/geneticAlgorithm/run_algorithm.py"
    return {"python": sys.version, "executable": sys.executable, "cwd": str(cwd),
            "required_runtime_path": str(required_runtime_path), "required_runtime_path_exists": required_runtime_path.is_file(),
            "runtime_sha256": runtime_sha256(),
            "selected_graphs": {name: graph_parameters(name) for name in ("er4", "ws3", "ba")},
            "versions": {p: importlib.metadata.version(p) for p in ("numpy", "jmetalpy", "ray", "scikit-learn")},
            "implementation_sha256": implementation_sha256(),
            "benchmark": problem.benchmark_metadata() if hasattr(problem, "benchmark_metadata") else {"name": problem.get_name()},
            "configuration": load_configuration()}


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def topology_metrics(args, adjacency):
    normalized = {
        str(source): [int(target) for target in targets]
        for source, targets in sorted(adjacency.items())
    }
    canonical = json.dumps(
        normalized, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    edges = [(source, target) for source, targets in adjacency.items() for target in targets]
    unique_edges = set(edges)
    self_loops = [(source, target) for source, target in edges if source == target]
    out_degrees = {source: len(targets) for source, targets in adjacency.items()}
    in_degrees = {island: 0 for island in range(args.islands)}
    for _, target in edges:
        in_degrees[target] += 1

    def degree_summary(mapping):
        values = list(mapping.values())
        return {
            "min": min(values) if values else None,
            "mean": sum(values) / len(values) if values else None,
            "max": max(values) if values else None,
            "values_by_island": {
                str(island): degree for island, degree in mapping.items()
            },
        }

    def reachable(start, graph):
        seen = {start}
        stack = [start]
        while stack:
            node = stack.pop()
            for neighbour in graph[node]:
                if neighbour not in seen:
                    seen.add(neighbour)
                    stack.append(neighbour)
        return seen

    forward = {island: set(adjacency[island]) for island in range(args.islands)}
    reverse = {island: set() for island in range(args.islands)}
    undirected = {island: set() for island in range(args.islands)}
    for source, target in unique_edges:
        reverse[target].add(source)
        undirected[source].add(target)
        undirected[target].add(source)
    strongly_connected = (
        len(reachable(0, forward)) == args.islands
        and len(reachable(0, reverse)) == args.islands
    )
    weakly_connected = len(reachable(0, undirected)) == args.islands
    possible_non_loop_edges = args.islands * max(0, args.islands - 1)
    unique_non_loop_edges = sum(1 for source, target in unique_edges if source != target)
    shape = torus_shape(args)
    result = {
        "adjacency_sha256": hashlib.sha256(canonical).hexdigest(),
        "node_count": args.islands,
        "directed_edge_count_with_multiplicity": len(edges),
        "unique_directed_edge_count": len(unique_edges),
        "self_loop_count_with_multiplicity": len(self_loops),
        "duplicate_directed_edge_count": len(edges) - len(unique_edges),
        "reciprocal_unique_directed_edge_count": sum(
            1 for source, target in unique_edges if (target, source) in unique_edges
        ),
        "directed_density_excluding_self_loops": (
            unique_non_loop_edges / possible_non_loop_edges
            if possible_non_loop_edges
            else 0.0
        ),
        "out_degree": degree_summary(out_degrees),
        "in_degree": degree_summary(in_degrees),
        "zero_out_degree_islands": [
            island for island, degree in out_degrees.items() if degree == 0
        ],
        "zero_in_degree_islands": [
            island for island, degree in in_degrees.items() if degree == 0
        ],
        "weakly_connected": weakly_connected,
        "strongly_connected": strongly_connected,
    }
    if shape is not None:
        result["torus_coordinate_by_island"] = {
            str(island): {
                "row": island // shape["columns"],
                "column": island % shape["columns"],
            }
            for island in range(args.islands)
        }
    return result


def topology_payload(args, adjacency):
    return {
        "schema_version": 2,
        "name": args.topology,
        "islands": args.islands,
        "torus_shape": torus_shape(args),
        "parameters": selected_topology_parameters(args),
        "adjacency": adjacency,
        "graph_metrics": topology_metrics(args, adjacency),
        "note": "Exact outgoing neighbour lists; migration selects one destination per migrant",
    }


def save_topology(directory, args, adjacency):
    dump(directory / "topology.json", topology_payload(args, adjacency))
    # Post-run plot: exact adjacency stays in JSON, including loops/direction.
    import math
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    xy = [(math.cos(2 * math.pi * i / args.islands), math.sin(2 * math.pi * i / args.islands)) for i in range(args.islands)]
    fig, ax = plt.subplots(figsize=(9, 9))
    edges = [(xy[i], xy[j]) for i, targets in adjacency.items() for j in targets if i != j]
    ax.add_collection(LineCollection(edges, colors="gray", linewidths=.25, alpha=.2))
    ax.scatter(*zip(*xy), s=15, color="black")
    if args.islands <= 40:
        for i, (x, y) in enumerate(xy):
            ax.text(x * 1.06, y * 1.06, str(i), ha="center", va="center", fontsize=8)
    ax.set(xlim=(-1.2, 1.2), ylim=(-1.2, 1.2), aspect="equal",
           title=f"{args.topology}, {args.islands} islands (adjacency view)")
    ax.axis("off")
    fig.savefig(directory / "topology.png", dpi=160)
    plt.close(fig)


def run(args):
    env = environment(args)
    os.environ.update(env)
    os.chdir(PACKAGE_ROOT)
    configuration, problem, topology_class, adjacency = validate(args)
    topology_parameters = selected_topology_parameters(args)
    required_cpus = 2 * args.islands + 1  # Existing Island, Computation and SignalActor reservations.
    required_slurm_cpus = required_cpus + 1  # One physical head CPU is reserved for the driver.
    if args.dry_run:
        print(json.dumps({"problem": problem.get_name(), "dimension": args.dimension,
                          "evaluations": args.evaluations, "population": args.population,
                          "offspring": args.offspring, "migrants": args.migrants, "interval": args.interval,
                          "islands": args.islands, "strategy": args.strategy, "acceptance": args.acceptance,
                          "topology": args.topology, "required_ray_cpus": required_cpus,
                          "required_slurm_cpus": required_slurm_cpus,
                          "topology_parameters": topology_parameters,
                          "actor_startup_timeout": args.actor_startup_timeout,
                          "seed_base_for_repeat": int(env["ISLANDS_SEED"]),
                          "metrics_profile": "research-v1-full-buffered",
                          "effect_horizon_steps": int(env["ISLANDS_EFFECT_HORIZON_STEPS"]),
                          "delivery_ack_timeout_seconds": float(env["ISLANDS_DELIVERY_TIMEOUT_SECONDS"]),
                          "diagnostic": args.diagnostic, "dry_run": True}, indent=2))
        return

    import ray
    from ray.util.scheduling_strategies import NodeAffinitySchedulingStrategy
    from islands_desync.geneticAlgorithm.run_hpc.run_algorithm_params import RunAlgorithmParams
    from islands_desync.geneticAlgorithm.run_hpc.benchmark_configuration import runtime_sha256
    from islands_desync.geneticAlgorithm.utils.filename import Filename
    from islands_desync.islands.core.IslandRunner import IslandRunner
    from islands_desync.islands.selectAlgorithm import RandomSelect

    now = datetime.now()
    date, token = now.strftime("%y%m%d"), now.strftime("%H%M%S") + "_" + uuid.uuid4().hex[:10]
    params = RunAlgorithmParams(args.islands, args.migrants, args.interval, date, token,
                                args.repeat, args.topology, args.strategy, args.acceptance,
                                torus_rows=args.torus_rows, torus_columns=args.torus_columns,
                                actor_startup_timeout=args.actor_startup_timeout)
    raw = Path(Filename(None, False).getpath(date, problem.get_name()[:4], args.dimension, token,
               args.islands, args.strategy[0], args.topology[0], args.interval, args.migrants)).resolve()
    if raw.exists():
        raise FileExistsError(raw)
    run_id = f"{date}_{token}"
    audit = Path(env["ISLANDS_AUDIT_ROOT"]) / run_id
    audit.mkdir(parents=True, exist_ok=False)
    versions = {p: importlib.metadata.version(p) for p in ("numpy", "jmetalpy", "ray", "scikit-learn")}
    git = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True)
    benchmark_metadata = problem.benchmark_metadata() if hasattr(problem, "benchmark_metadata") else {"name": problem.get_name()}
    scientific_configuration = {
        "study": "diagnostic" if args.diagnostic else "approved-144",
        "benchmark": benchmark_metadata,
        "algorithm_configuration": configuration,
        "dimension": args.dimension,
        "islands": args.islands,
        "evaluations_per_island": args.evaluations,
        "population": args.population,
        "offspring": args.offspring,
        "migration": {
            "group_size": args.migrants,
            "interval": args.interval,
            "interval_unit": "evaluation-count difference",
            "selection": args.strategy,
            "acceptance": args.acceptance,
        },
        "topology": {
            "name": args.topology,
            "parameters": topology_parameters,
            "adjacency_sha256": topology_metrics(args, adjacency)["adjacency_sha256"],
        },
        "repeat": args.repeat,
        "seed": {
            "requested_base": args.seed,
            "repeat_base": int(env["ISLANDS_SEED"]),
            "island_seed_formula": "repeat_base + island_index",
        },
        "metrics": {
            "profile": "research-v1-full-buffered",
            "effect_horizon_steps": int(env["ISLANDS_EFFECT_HORIZON_STEPS"]),
            "delivery_ack_timeout_seconds": float(env["ISLANDS_DELIVERY_TIMEOUT_SECONDS"]),
        },
    }
    experiment_key_payload = dict(scientific_configuration)
    experiment_key_payload.pop("repeat")
    experiment_key_payload.pop("seed")
    experiment_key = hashlib.sha256(
        json.dumps(experiment_key_payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()
    configuration_sha256 = hashlib.sha256(
        json.dumps(scientific_configuration, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()
    slurm_metadata = {
        key: os.environ.get(key)
        for key in (
            "SLURM_JOB_ID", "SLURM_ARRAY_JOB_ID", "SLURM_ARRAY_TASK_ID",
            "SLURM_JOB_NAME", "SLURM_JOB_ACCOUNT", "SLURM_JOB_PARTITION",
            "SLURM_JOB_NODELIST", "SLURM_JOB_NUM_NODES", "SLURM_NNODES",
            "SLURM_JOB_CPUS_PER_NODE", "SLURM_CPUS_PER_TASK", "SLURM_NTASKS",
            "SLURM_MEM_PER_CPU", "SLURM_MEM_PER_NODE", "SLURM_SUBMIT_DIR",
            "SLURM_SUBMIT_HOST", "ISLANDS_ALLOCATED_CPUS_PER_NODE",
        )
    }
    manifest = {"schema_version": 2, "status": "starting", "run_id": run_id,
                "experiment_key": experiment_key, "configuration_sha256": configuration_sha256,
                "args": vars(args), "configuration": configuration,
                "run_directory": str(raw), "versions": versions, "git_commit": git.stdout.strip() or None,
                "git_dirty": bool(dirty.stdout) if dirty.returncode == 0 else None,
                "runtime_sha256": runtime_sha256(),
                "selected_graphs": {name: graph_parameters(name) for name in ("er4", "ws3", "ba")},
                "launcher_sha256": hashlib.sha256(Path(__file__).read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
                "started_utc": datetime.now(timezone.utc).isoformat(),
                "invocation": {"argv": sys.argv, "cwd": str(Path.cwd()), "hostname": socket.gethostname(),
                               "user": os.environ.get("USER"), "platform": platform.platform(),
                               "python_executable": sys.executable},
                "slurm": slurm_metadata,
                "environment": env, "required_ray_cpus": required_cpus,
                "required_slurm_cpus": required_slurm_cpus,
                "topology_parameters": topology_parameters,
                "metrics_profile": {
                    "name": "research-v1-full-buffered",
                    "effect_horizon_steps": int(env["ISLANDS_EFFECT_HORIZON_STEPS"]),
                    "delivery_ack_timeout_seconds": float(
                        env["ISLANDS_DELIVERY_TIMEOUT_SECONDS"]
                    ),
                    "migration_events": "gzip JSONL, buffered per island",
                    "fitness_history": "initial plus every step",
                    "synchronous_writes_during_optimization": False,
                },
                "delay_definition": "source_epoch_at_send - destination_epoch_at_receive",
                "migration_interval_unit": "evaluation-count difference (existing main implementation)",
                "benchmark": benchmark_metadata,
                "scientific_configuration": scientific_configuration,
                "storage": {
                    "scratch_environment": os.environ.get("SCRATCH"),
                    "using_home_fallback": env["ISLANDS_STORAGE_FALLBACK"] == "1",
                    "storage_root": env["ISLANDS_STORAGE_ROOT"],
                    "raw_results_root": env["ISLANDS_RUN_OUTPUT_ROOT"],
                    "audit_root": env["ISLANDS_AUDIT_ROOT"],
                    "pilot_artifact_root": env["ISLANDS_ARTIFACT_ROOT"],
                    "slurm_log_directory": env["ISLANDS_SLURM_LOG_DIR"],
                    "checkpoint_root": env["ISLANDS_CHECKPOINT_ROOT"],
                    "persistent_tmp_root": env["ISLANDS_TMP_ROOT"],
                    "ray_temp_directory": os.environ.get("RAY_TMPDIR") or args.ray_temp_dir,
                    "note": "Ray and Matplotlib use node-local /tmp on Ares; persistent outputs use SCRATCH.",
                }}
    run_metadata = {
        "schema_version": 1,
        "run_id": run_id,
        "experiment_key": experiment_key,
        "configuration_sha256": configuration_sha256,
        "status": "starting",
        "started_utc": manifest["started_utc"],
        "scientific_configuration": scientific_configuration,
        "resources": {
            "required_ray_cpus": required_cpus,
            "required_slurm_cpus": required_slurm_cpus,
            "slurm": slurm_metadata,
        },
        "provenance": {
            "git_commit": manifest["git_commit"],
            "git_dirty": manifest["git_dirty"],
            "runtime_sha256": manifest["runtime_sha256"],
            "launcher_sha256": manifest["launcher_sha256"],
            "versions": versions,
        },
        "storage": manifest["storage"],
        "outputs": {
            "run_directory": str(raw),
            "audit_directory": str(audit),
        },
    }
    dump(audit / "experiment_manifest.json", manifest)
    dump(audit / "run_metadata.json", run_metadata)
    dump(audit / "topology.json", topology_payload(args, adjacency))
    print(f"EXPERIMENT_AUDIT={audit}", flush=True)
    try:
        if args.ray_address == "local":
            if args.local_cpus < required_cpus:
                raise ValueError(f"Local mode needs at least {required_cpus} Ray CPUs")
            kwargs = {"num_cpus": args.local_cpus, "include_dashboard": False, "runtime_env": {"env_vars": env}}
            if args.ray_temp_dir:
                kwargs["_temp_dir"] = args.ray_temp_dir
            ray.init(address="local", **kwargs)
        else:
            deadline = time.monotonic() + args.startup_timeout
            while True:
                try:
                    ray.init(address=args.ray_address, runtime_env={"env_vars": env})
                    break
                except (ConnectionError, RuntimeError):
                    if time.monotonic() >= deadline:
                        raise
                    time.sleep(2)
        deadline = time.monotonic() + args.startup_timeout
        expected_nodes = int(os.environ.get("SLURM_JOB_NUM_NODES", "1"))
        while True:
            nodes = [node for node in ray.nodes() if node["Alive"]]
            if len(nodes) >= expected_nodes:
                break
            if time.monotonic() >= deadline:
                raise RuntimeError(f"Only {len(nodes)}/{expected_nodes} Ray nodes joined")
            time.sleep(1)
        if ray.cluster_resources().get("CPU", 0) < required_cpus:
            raise RuntimeError(f"Insufficient Ray CPUs: need {required_cpus}; got {ray.cluster_resources()}")
        probe = ray.remote(num_cpus=0)(node_probe)
        probes = ray.get([probe.options(scheduling_strategy=NodeAffinitySchedulingStrategy(node["NodeID"], soft=False)).remote(
            configuration["problem"], args.dimension) for node in nodes], timeout=args.startup_timeout)
        baseline = probes[0]
        for entry in probes:
            if any(entry[key] != baseline[key] for key in ("implementation_sha256", "runtime_sha256", "selected_graphs", "benchmark", "configuration", "python", "versions")):
                raise RuntimeError("Ray nodes disagree on code, benchmark instance, Python or configuration")
            if (entry["runtime_sha256"] != manifest["runtime_sha256"] or entry["versions"] != versions
                    or entry["selected_graphs"] != manifest["selected_graphs"]):
                raise RuntimeError("Worker runtime/dependencies differ from the driver")
            if hasattr(problem, "benchmark_metadata") and entry["benchmark"] != manifest["benchmark"]:
                raise RuntimeError("Worker benchmark differs from the driver")
            if Path(entry["cwd"]).resolve() != PACKAGE_ROOT.resolve() or not entry["required_runtime_path_exists"]:
                raise RuntimeError(
                    f"Worker has invalid runtime CWD/path: cwd={entry['cwd']} "
                    f"required={entry['required_runtime_path']}"
                )
        manifest.update({"status": "running", "node_checks": probes, "ray_resources": ray.cluster_resources()})
        run_metadata.update({"status": "running", "ray_resources": manifest["ray_resources"]})
        dump(audit / "experiment_manifest.json", manifest)
        dump(audit / "run_metadata.json", run_metadata)
        results = ray.get(IslandRunner(topology_class, RandomSelect, params).create())
        if len(results) != args.islands:
            raise RuntimeError("Not all islands returned results")
        for island in range(args.islands):
            for name in (f"resultsEveryStepW{island}.json", f"W{island} Imigrants.json", f"kontrolW{island}End.ctrl.txt"):
                if not (raw / name).is_file():
                    raise RuntimeError(f"Missing island output: {raw / name}")
            metrics_directory = raw / "metrics" / f"island_{island:03d}"
            for name in (
                "migration_events.jsonl.gz",
                "queue_fetches.jsonl.gz",
                "fitness_history.jsonl.gz",
                "final_solution.json",
                "runtime.json",
                "summary.json",
            ):
                if not (metrics_directory / name).is_file():
                    raise RuntimeError(
                        f"Missing research metric: {metrics_directory / name}"
                    )
        if not (raw / "metrics" / "data_contract.json").is_file():
            raise RuntimeError("Missing research metrics data contract")
        benchmark_run_metadata = json.loads(
            (raw / "benchmark_manifest.json").read_text(encoding="utf-8")
        )
        run_metadata["active_operators"] = benchmark_run_metadata.get(
            "active_operators"
        )
        dump(raw / "iterations_per_second.json", {str(r["island"]): r for r in results})
        save_topology(audit, args, adjacency)
        manifest.update({"status": "complete", "completed_utc": datetime.now(timezone.utc).isoformat(), "islands_completed": len(results)})
        run_metadata.update({"status": "complete", "completed_utc": manifest["completed_utc"], "islands_completed": len(results)})
        print(f"BENCHMARK_RUN_OK={raw}", flush=True)
    except BaseException as error:
        manifest.update({"status": "failed", "error": repr(error)})
        run_metadata.update({"status": "failed", "failed_utc": datetime.now(timezone.utc).isoformat(), "error": repr(error)})
        raise
    finally:
        dump(audit / "experiment_manifest.json", manifest)
        dump(audit / "run_metadata.json", run_metadata)
        if raw.is_dir():
            for name in ("experiment_manifest.json", "run_metadata.json", "topology.json", "topology.png"):
                if (audit / name).exists():
                    shutil.copy2(audit / name, raw / name)
        if args.result_pointer:
            pointer = Path(args.result_pointer).resolve()
            pointer.parent.mkdir(parents=True, exist_ok=True)
            dump(pointer, {"schema_version": 2, "status": manifest["status"], "run_id": run_id,
                           "experiment_key": experiment_key, "run_directory": str(raw),
                           "audit_directory": str(audit),
                           "experiment_manifest": str(audit / "experiment_manifest.json"),
                           "run_metadata": str(audit / "run_metadata.json")})
        ray.shutdown()


if __name__ == "__main__":
    run(parser().parse_args())
