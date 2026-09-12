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
import shutil
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT / "islands_desync"
sys.path.insert(0, str(PACKAGE_ROOT))

TOPOLOGIES = {name: name for name in ("ER1", "ER2", "ER3", "ER4", "WS3", "WS4")}
TOPOLOGIES = {key.lower(): value + "Topology" for key, value in TOPOLOGIES.items()}
TOPOLOGIES.update({"ring": "RingTopology", "torus": "TorusTopology", "complete": "CompleteTopology"})
ACCEPTANCE = {"plain", "better", "newer", "older", "oldest", "stochastic", "rejectTooOld", "window"}


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--problem", required=True)
    p.add_argument("--dimension", type=int, required=True)
    p.add_argument("--islands", type=int, default=180)
    p.add_argument("--evaluations", type=int, default=8000)
    p.add_argument("--population", type=int, default=16)
    p.add_argument("--offspring", type=int, default=4)
    p.add_argument("--migrants", type=int, default=5)
    p.add_argument("--interval", type=int, default=5)
    p.add_argument("--topology", choices=TOPOLOGIES, default="complete")
    p.add_argument("--strategy", choices=("best", "random", "maxDistance", "worst"), default="random")
    p.add_argument("--acceptance", default="plain")
    p.add_argument("--repeat", type=int, default=1)
    p.add_argument("--seed", type=int, default=20260912)
    p.add_argument("--ray-address", default="auto")
    p.add_argument("--local-cpus", type=int, default=6)
    p.add_argument("--ray-temp-dir")
    p.add_argument("--startup-timeout", type=float, default=120)
    p.add_argument("--dry-run", action="store_true")
    return p


def environment(args):
    return {
        "ISLANDS_CONFIG": str(Path(os.environ.get("ISLANDS_CONFIG", str(PACKAGE_ROOT / "islands_desync/geneticAlgorithm/algorithm/configurations/algorithm_configuration.json"))).resolve()),
        "ISLANDS_PROBLEM": args.problem.strip().lower(),
        "ISLANDS_NUMBER_OF_VARIABLES": str(args.dimension),
        "ISLANDS_NUMBER_OF_EVALUATIONS": str(args.evaluations),
        "ISLANDS_POPULATION_SIZE": str(args.population),
        "ISLANDS_OFFSPRING_POPULATION_SIZE": str(args.offspring),
        "ISLANDS_SEED": str(args.seed + (args.repeat - 1) * 1000000),
        "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1", "MPLBACKEND": "Agg",
        "PYTHONPATH": str(PACKAGE_ROOT) + os.pathsep + os.environ.get("PYTHONPATH", ""),
    }


def validate(args):
    from islands_desync.geneticAlgorithm.run_hpc.benchmark_configuration import create_problem, load_configuration
    if args.islands < 1 or args.repeat < 1 or args.seed < 0 or args.interval < 1:
        raise ValueError("islands/repeat/interval must be positive and seed nonnegative")
    if not 1 <= args.migrants <= args.population:
        raise ValueError("migrants must be between 1 and population size")
    if args.startup_timeout <= 0 or args.local_cpus < 1:
        raise ValueError("startup-timeout and local-cpus must be positive")
    acceptance = args.acceptance.removeprefix("dup_").split(":", 1)
    if acceptance[0] not in ACCEPTANCE:
        raise ValueError("Unknown acceptance strategy")
    if len(acceptance) == 2:
        int(acceptance[1])
    if args.topology == "torus" and (args.islands % 12 or args.islands < 24):
        raise ValueError("The existing torus requires 12 x (islands/12), with islands >= 24 and divisible by 12")
    configuration = load_configuration()
    problem = create_problem(configuration["problem"], configuration["number_of_variables"])
    name = TOPOLOGIES[args.topology]
    cls = getattr(importlib.import_module("islands_desync.islands.topologies." + name), name)
    with contextlib.redirect_stdout(io.StringIO()):
        topology = cls(args.islands, lambda i: i)
        try:
            adjacency = topology.create(12, args.islands // 12) if args.topology == "torus" else topology.create()
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
    return {"python": sys.version, "executable": sys.executable, "runtime_sha256": runtime_sha256(),
            "versions": {p: importlib.metadata.version(p) for p in ("numpy", "jmetalpy", "ray", "scikit-learn")},
            "implementation_sha256": implementation_sha256(),
            "benchmark": problem.benchmark_metadata() if hasattr(problem, "benchmark_metadata") else {"name": problem.get_name()},
            "configuration": load_configuration()}


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def save_topology(directory, args, adjacency):
    dump(directory / "topology.json", {"name": args.topology, "islands": args.islands,
         "torus_shape": [12, args.islands // 12] if args.topology == "torus" else None,
         "adjacency": adjacency, "note": "Exact outgoing neighbour lists; migration selects one destination per migrant"})
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
    required_cpus = 2 * args.islands + 1  # Existing Island, Computation and SignalActor reservations.
    if args.dry_run:
        print(json.dumps({"problem": problem.get_name(), "dimension": args.dimension,
                          "evaluations": args.evaluations, "population": args.population,
                          "offspring": args.offspring, "migrants": args.migrants, "interval": args.interval,
                          "islands": args.islands, "strategy": args.strategy, "acceptance": args.acceptance,
                          "topology": args.topology, "required_ray_cpus": required_cpus,
                          "seed_base_for_repeat": int(env["ISLANDS_SEED"]),
                          "dry_run": True}, indent=2))
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
                                args.repeat, args.topology, args.strategy, args.acceptance)
    raw = Path(Filename(None, False).getpath(date, problem.get_name()[:4], args.dimension, token,
               args.islands, args.strategy[0], args.topology[0], args.interval, args.migrants)).resolve()
    if raw.exists():
        raise FileExistsError(raw)
    audit = ROOT / "hpc_benchmarks/results" / f"{date}_{token}"
    audit.mkdir(parents=True, exist_ok=False)
    versions = {p: importlib.metadata.version(p) for p in ("numpy", "jmetalpy", "ray", "scikit-learn")}
    git = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True)
    manifest = {"status": "starting", "args": vars(args), "configuration": configuration,
                "run_directory": str(raw), "versions": versions, "git_commit": git.stdout.strip() or None,
                "git_dirty": bool(dirty.stdout) if dirty.returncode == 0 else None,
                "runtime_sha256": runtime_sha256(),
                "launcher_sha256": hashlib.sha256(Path(__file__).read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
                "started_utc": datetime.now(timezone.utc).isoformat(),
                "slurm": {k: os.environ.get(k) for k in ("SLURM_JOB_ID", "SLURM_JOB_NODELIST", "SLURM_JOB_NUM_NODES", "SLURM_JOB_CPUS_PER_NODE", "ISLANDS_ALLOCATED_CPUS_PER_NODE")},
                "environment": env, "required_ray_cpus": required_cpus,
                "delay_definition": "source_epoch_at_send - destination_epoch_at_receive",
                "migration_interval_unit": "evaluation-count difference (existing main implementation)",
                "benchmark": problem.benchmark_metadata() if hasattr(problem, "benchmark_metadata") else {"name": problem.get_name()}}
    dump(audit / "experiment_manifest.json", manifest)
    dump(audit / "topology.json", {"name": args.topology, "adjacency": adjacency})
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
            if any(entry[key] != baseline[key] for key in ("implementation_sha256", "runtime_sha256", "benchmark", "configuration", "python", "versions")):
                raise RuntimeError("Ray nodes disagree on code, benchmark instance, Python or configuration")
            if entry["runtime_sha256"] != manifest["runtime_sha256"] or entry["versions"] != versions:
                raise RuntimeError("Worker runtime/dependencies differ from the driver")
            if hasattr(problem, "benchmark_metadata") and entry["benchmark"] != manifest["benchmark"]:
                raise RuntimeError("Worker benchmark differs from the driver")
        manifest.update({"status": "running", "node_checks": probes, "ray_resources": ray.cluster_resources()})
        dump(audit / "experiment_manifest.json", manifest)
        results = ray.get(IslandRunner(topology_class, RandomSelect, params).create())
        if len(results) != args.islands:
            raise RuntimeError("Not all islands returned results")
        for island in range(args.islands):
            for name in (f"resultsEveryStepW{island}.json", f"W{island} Imigrants.json", f"kontrolW{island}End.ctrl.txt"):
                if not (raw / name).is_file():
                    raise RuntimeError(f"Missing island output: {raw / name}")
        dump(raw / "iterations_per_second.json", {str(r["island"]): r for r in results})
        save_topology(audit, args, adjacency)
        manifest.update({"status": "complete", "completed_utc": datetime.now(timezone.utc).isoformat(), "islands_completed": len(results)})
        print(f"BENCHMARK_RUN_OK={raw}", flush=True)
    except BaseException as error:
        manifest.update({"status": "failed", "error": repr(error)})
        raise
    finally:
        dump(audit / "experiment_manifest.json", manifest)
        if raw.is_dir():
            for name in ("experiment_manifest.json", "topology.json", "topology.png"):
                if (audit / name).exists():
                    shutil.copy2(audit / name, raw / name)
        ray.shutdown()


if __name__ == "__main__":
    run(parser().parse_args())
