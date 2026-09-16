#!/usr/bin/env python3
"""Run one sharded 144-island study configuration on one Athena A100."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
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
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(PACKAGE_ROOT))

from athena_gpu.study_contract import (
    RAY_CPUS,
    SLURM_CPUS,
    STUDY_ISLANDS,
    STUDY_SHARDS,
    build_study_plan,
)
from athena_gpu.environment_contract import environment_report
from hpc_benchmarks import run_benchmark as common
from islands_desync.geneticAlgorithm.utils.benchmarks_refined.discrete import (
    DEFAULT_INSTANCE_SEED,
)


GIB = 1024 ** 3


def parser() -> argparse.ArgumentParser:
    result = common.parser()
    result.description = __doc__
    result.set_defaults(ray_address="local", local_cpus=RAY_CPUS)
    result.add_argument("--shards", type=int, default=STUDY_SHARDS)
    result.add_argument("--instance-seed", type=int, default=DEFAULT_INSTANCE_SEED)
    result.add_argument("--initial-max-wait-ms", type=float, default=50.0)
    result.add_argument("--steady-max-wait-ms", type=float, default=2.0)
    result.add_argument("--ray-memory-gib", type=int, default=96)
    result.add_argument("--object-store-gib", type=int, default=8)
    result.add_argument("--operation-timeout-seconds", type=float, default=300.0)
    result.add_argument("--run-timeout-seconds", type=float, default=3300.0)
    result.add_argument("--finalization-timeout-seconds", type=float, default=1200.0)
    result.add_argument("--confirm-study-144", action="store_true")
    return result


def _athena_runtime_sha256() -> str:
    digest = hashlib.sha256()
    paths = sorted((ROOT / "athena_gpu").glob("*.py"), key=lambda path: path.name)
    for path in paths:
        digest.update(path.name.encode("utf-8") + b"\0")
        digest.update(path.read_bytes().replace(b"\r\n", b"\n") + b"\0")
    return digest.hexdigest()


def _git_state() -> tuple[str | None, bool | None]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return commit.stdout.strip() or None, bool(dirty.stdout) if dirty.returncode == 0 else None


def _validate_scientific_contract(args) -> dict:
    if args.topology == "er4":
        raise ValueError("ER4 remains blocked: the supplied graph has 150 rather than 144 nodes")
    configuration, problem, topology_class, adjacency = common.validate(args)
    from islands_desync.geneticAlgorithm.utils import benchmarks_refined

    if not benchmarks_refined.is_registered_problem(args.problem):
        raise ValueError("Athena GPU study runner supports only the registered 40-function suite")
    if args.ray_address != "local" or args.local_cpus != RAY_CPUS:
        raise ValueError("Athena sharded runner requires a local 15-CPU Ray instance")
    if args.instance_seed < 0:
        raise ValueError("instance-seed must be nonnegative")
    for name in (
        "operation_timeout_seconds",
        "run_timeout_seconds",
        "finalization_timeout_seconds",
    ):
        if getattr(args, name) <= 0:
            raise ValueError(f"{name} must be positive")
    if args.ray_memory_gib != 96 or args.object_store_gib != 8:
        raise ValueError("use the validated Athena 96/8 GiB Ray memory profile")
    if not args.diagnostic:
        expected = {
            "islands": 144,
            "shards": 12,
            "evaluations": 8000,
            "population": 16,
            "offspring": 4,
            "migrants": 5,
            "interval": 5,
            "acceptance": "plain",
        }
        for name, value in expected.items():
            if getattr(args, name) != value:
                raise ValueError(f"normal study run requires {name}={value!r}")
        if args.strategy not in ("best", "random", "maxDistance"):
            raise ValueError("normal matrix uses best, random or maxDistance")
        if args.repeat not in (1, 2, 3):
            raise ValueError("normal matrix repeat must be 1, 2 or 3")
        if not args.dry_run and not args.confirm_study_144:
            raise ValueError("full execution requires --confirm-study-144")
    plan = build_study_plan(
        islands=args.islands,
        shards=args.shards,
        population=args.population,
        offspring=args.offspring,
        evaluations=args.evaluations,
        diagnostic=args.diagnostic,
        initial_max_wait_ms=args.initial_max_wait_ms,
        steady_max_wait_ms=args.steady_max_wait_ms,
    )
    return {
        "configuration": configuration,
        "problem": problem,
        "topology_class": topology_class,
        "adjacency": adjacency,
        "plan": plan,
    }


def _require_compute_allocation(args) -> str:
    job_id = os.environ.get("SLURM_JOB_ID")
    if not job_id or socket.gethostname().split(".")[0].startswith("login"):
        raise RuntimeError("run only inside an Athena SLURM GPU allocation")
    if int(os.environ.get("SLURM_CPUS_PER_TASK", "0")) != SLURM_CPUS:
        raise RuntimeError("Athena study job requires --cpus-per-task=16")
    if not os.environ.get("CUDA_VISIBLE_DEVICES"):
        raise RuntimeError("Athena study job has no allocated CUDA device")
    expected_temp = f"/tmp/r{job_id}"
    if not args.ray_temp_dir or str(Path(args.ray_temp_dir)) != expected_temp:
        raise RuntimeError(f"Ray temp directory must be {expected_temp}")
    dependency_report = environment_report()
    if dependency_report["status"] != "passed":
        raise RuntimeError(
            "unexpected Athena Python/dependency stack: "
            + "; ".join(dependency_report["errors"])
        )
    commit, dirty = _git_state()
    expected_commit = os.environ.get("ATHENA_EXPECTED_COMMIT")
    if not expected_commit or commit != expected_commit or dirty is not False:
        raise RuntimeError("execution requires the pinned clean checkout throughout the job")
    return commit


def _slurm_metadata() -> dict:
    return {
        key: os.environ.get(key)
        for key in (
            "SLURM_JOB_ID",
            "SLURM_JOB_NAME",
            "SLURM_JOB_ACCOUNT",
            "SLURM_JOB_PARTITION",
            "SLURM_JOB_NODELIST",
            "SLURM_JOB_NUM_NODES",
            "SLURM_CPUS_PER_TASK",
            "SLURM_MEM_PER_NODE",
            "SLURM_SUBMIT_DIR",
            "SLURM_SUBMIT_HOST",
        )
    }


def _scientific_configuration(args, env, configuration, problem, adjacency) -> dict:
    topology_parameters = common.selected_topology_parameters(args)
    benchmark = (
        problem.benchmark_metadata()
        if hasattr(problem, "benchmark_metadata")
        else {"name": problem.get_name()}
    )
    return {
        "study": "diagnostic" if args.diagnostic else "approved-144",
        "execution_backend": "athena-gpu-sharded",
        "benchmark": benchmark,
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
            "adjacency_sha256": common.topology_metrics(args, adjacency)["adjacency_sha256"],
        },
        "repeat": args.repeat,
        "seed": {
            "requested_base": args.seed,
            "repeat_base": int(env["ISLANDS_SEED"]),
            "island_seed_formula": "repeat_base + island_index",
            "benchmark_instance_seed": args.instance_seed,
        },
        "metrics": {
            "profile": "research-v1-full-buffered",
            "effect_horizon_steps": int(env["ISLANDS_EFFECT_HORIZON_STEPS"]),
            "delivery_ack_timeout_seconds": float(env["ISLANDS_DELIVERY_TIMEOUT_SECONDS"]),
            "athena_evaluation_telemetry": True,
        },
    }


def _fingerprints(scientific_configuration) -> tuple[str, str]:
    key_payload = dict(scientific_configuration)
    key_payload.pop("repeat")
    key_payload.pop("seed")
    experiment_key = hashlib.sha256(
        json.dumps(key_payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()
    configuration_sha256 = hashlib.sha256(
        json.dumps(
            scientific_configuration,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    return experiment_key, configuration_sha256


def _write_athena_contract(directory: Path, *, plan: dict, backend: dict, shards: list[dict], router: dict) -> None:
    common.dump(directory / "backend.json", backend)
    common.dump(directory / "shards.json", {"schema_version": 1, "placements": shards})
    common.dump(directory / "migration_router.json", router)
    common.dump(
        directory / "athena_evaluation_contract.json",
        {
            "schema_version": 1,
            "profile": plan["profile"],
            "request_identity": "request_id is unique within run_id",
            "row_order": "responses preserve request and row order",
            "failure_policy": "GPU failures fail the run; no CPU fallback or retry",
            "dispatch_reasons": ["size", "timeout", "flush"],
            "generation_barrier": False,
            "files": {
                "evaluation_requests.jsonl.gz": "one terminal record per logical-island evaluation request",
                "gpu_batches.jsonl.gz": "one record per physical GPU backend call",
                "summary.json": "request, response, row and batch reconciliation",
                "backend.json": "A100/CuPy/Ray identity and total calls/rows",
                "shards.json": "stable logical-island placement",
                "migration_router.json": "global queue and barrier counters",
            },
        },
    )


def _basic_output_check(raw: Path, args, results, batch_summary) -> None:
    expected_steps = (args.evaluations - args.population) // args.offspring
    if len(results) != args.islands or {item["island"] for item in results} != set(range(args.islands)):
        raise RuntimeError("not every logical island returned a result")
    for item in results:
        if item["iterations"] != expected_steps or item["evaluations"] != args.evaluations:
            raise RuntimeError(f"island {item['island']} has an incorrect evaluation budget")
    expected_requests = args.islands * (expected_steps + 1)
    expected_rows = args.islands * args.evaluations
    if batch_summary.get("request_count") != expected_requests:
        raise RuntimeError("evaluation request reconciliation failed")
    if batch_summary.get("response_count") != expected_requests or batch_summary.get("error_count") != 0:
        raise RuntimeError("evaluation response reconciliation failed")
    if batch_summary.get("row_count") != expected_rows:
        raise RuntimeError("GPU row accounting differs from the scientific evaluation budget")
    for island in range(args.islands):
        for name in (
            f"resultsEveryStepW{island}.json",
            f"W{island} Imigrants.json",
            f"kontrolW{island}End.ctrl.txt",
        ):
            if not (raw / name).is_file():
                raise RuntimeError(f"missing island output: {raw / name}")
        metrics = raw / "metrics" / f"island_{island:03d}"
        for name in (
            "migration_events.jsonl.gz",
            "queue_fetches.jsonl.gz",
            "fitness_history.jsonl.gz",
            "final_solution.json",
            "runtime.json",
            "summary.json",
        ):
            if not (metrics / name).is_file():
                raise RuntimeError(f"missing research metric: {metrics / name}")


def run(args) -> None:
    env = common.environment(args)
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env["PYTHONPATH"]
    os.environ.update(env)
    os.chdir(PACKAGE_ROOT)
    validated = _validate_scientific_contract(args)
    configuration = validated["configuration"]
    problem = validated["problem"]
    adjacency = validated["adjacency"]
    plan = validated["plan"]
    if args.dry_run:
        print(
            json.dumps(
                {
                    **plan,
                    "problem": problem.get_name(),
                    "dimension": args.dimension,
                    "topology": common.topology_payload(args, adjacency),
                    "migration": {
                        "group_size": args.migrants,
                        "interval": args.interval,
                        "selection": args.strategy,
                        "acceptance": args.acceptance,
                    },
                    "repeat": args.repeat,
                    "seed_base_for_repeat": int(env["ISLANDS_SEED"]),
                    "dry_run": True,
                },
                indent=2,
            )
        )
        return

    commit = _require_compute_allocation(args)
    import ray

    from athena_gpu.evaluation_batcher import make_actor_class as make_batcher
    from athena_gpu.gpu_evaluator import make_actor_class as make_gpu_evaluator
    from athena_gpu.island_shard import make_actor_class as make_island_shard
    from athena_gpu.migration_router import make_actor_class as make_router
    from islands_desync.geneticAlgorithm.run_hpc.benchmark_configuration import (
        runtime_sha256,
    )
    from islands_desync.geneticAlgorithm.run_hpc.run_algorithm_params import (
        RunAlgorithmParams,
    )
    from islands_desync.geneticAlgorithm.utils.filename import Filename

    now = datetime.now()
    date = now.strftime("%y%m%d")
    token = now.strftime("%H%M%S") + "_" + uuid.uuid4().hex[:10]
    run_id = f"{date}_{token}"
    params = RunAlgorithmParams(
        args.islands,
        args.migrants,
        args.interval,
        date,
        token,
        args.repeat,
        args.topology,
        args.strategy,
        args.acceptance,
        torus_rows=args.torus_rows,
        torus_columns=args.torus_columns,
        actor_startup_timeout=args.actor_startup_timeout,
    )
    raw = Path(
        Filename(None, False).getpath(
            date,
            problem.get_name()[:4],
            args.dimension,
            token,
            args.islands,
            args.strategy[0],
            args.topology[0],
            args.interval,
            args.migrants,
        )
    ).resolve()
    if raw.exists():
        raise FileExistsError(raw)
    audit = Path(env["ISLANDS_AUDIT_ROOT"]) / run_id
    audit.mkdir(parents=True, exist_ok=False)
    dependency_report = environment_report()
    versions = {
        name: installed[0]
        for name, installed in dependency_report["installed_expected_distributions"].items()
    }
    benchmark_metadata = problem.benchmark_metadata()
    scientific_configuration = _scientific_configuration(
        args, env, configuration, problem, adjacency
    )
    experiment_key, configuration_sha256 = _fingerprints(scientific_configuration)
    topology_parameters = common.selected_topology_parameters(args)
    slurm = _slurm_metadata()
    resources = plan["resources"]
    batching = plan["batching"]
    manifest = {
        "schema_version": 2,
        "status": "starting",
        "run_id": run_id,
        "experiment_key": experiment_key,
        "configuration_sha256": configuration_sha256,
        "args": vars(args),
        "configuration": configuration,
        "run_directory": str(raw),
        "versions": versions,
        "git_commit": commit,
        "git_dirty": False,
        "runtime_sha256": runtime_sha256(),
        "athena_runtime_sha256": _athena_runtime_sha256(),
        "selected_graphs": {
            name: common.graph_parameters(name) for name in ("er4", "ws3", "ba")
        },
        "launcher_sha256": hashlib.sha256(
            Path(__file__).read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest(),
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "invocation": {
            "argv": sys.argv,
            "cwd": str(Path.cwd()),
            "hostname": socket.gethostname(),
            "user": os.environ.get("USER"),
            "platform": platform.platform(),
            "python_executable": sys.executable,
        },
        "slurm": slurm,
        "environment": env,
        "execution_backend": "athena-gpu-sharded",
        "required_ray_cpus": resources["actor_cpus"],
        "ray_cluster_cpus": resources["ray_cpus"],
        "required_slurm_cpus": resources["slurm_cpus"],
        "topology_parameters": topology_parameters,
        "metrics_profile": {
            "name": "research-v1-full-buffered",
            "effect_horizon_steps": int(env["ISLANDS_EFFECT_HORIZON_STEPS"]),
            "delivery_ack_timeout_seconds": float(env["ISLANDS_DELIVERY_TIMEOUT_SECONDS"]),
            "migration_events": "gzip JSONL, buffered per logical island",
            "fitness_history": "initial plus every step",
            "athena_evaluation_requests": "gzip JSONL, buffered in shared batcher",
            "synchronous_writes_during_optimization": False,
        },
        "delay_definition": "source_epoch_at_send - destination_epoch_at_receive",
        "migration_interval_unit": "evaluation-count difference (existing main implementation)",
        "benchmark": benchmark_metadata,
        "scientific_configuration": scientific_configuration,
        "athena_plan": plan,
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
            "ray_temp_directory": args.ray_temp_dir,
            "note": "one-node Athena A100 job; persistent outputs use SCRATCH",
        },
    }
    run_metadata = {
        "schema_version": 1,
        "run_id": run_id,
        "experiment_key": experiment_key,
        "configuration_sha256": configuration_sha256,
        "status": "starting",
        "started_utc": manifest["started_utc"],
        "scientific_configuration": scientific_configuration,
        "execution_backend": "athena-gpu-sharded",
        "resources": {
            "required_ray_cpus": resources["actor_cpus"],
            "ray_cluster_cpus": resources["ray_cpus"],
            "required_slurm_cpus": resources["slurm_cpus"],
            "gpus": 1,
            "slurm": slurm,
        },
        "provenance": {
            "git_commit": commit,
            "git_dirty": False,
            "runtime_sha256": manifest["runtime_sha256"],
            "athena_runtime_sha256": manifest["athena_runtime_sha256"],
            "launcher_sha256": manifest["launcher_sha256"],
            "versions": versions,
        },
        "storage": manifest["storage"],
        "outputs": {"run_directory": str(raw), "audit_directory": str(audit)},
        "athena_plan": plan,
    }
    common.dump(audit / "experiment_manifest.json", manifest)
    common.dump(audit / "run_metadata.json", run_metadata)
    common.dump(audit / "topology.json", common.topology_payload(args, adjacency))
    print(f"EXPERIMENT_AUDIT={audit}", flush=True)

    ray_started = False
    try:
        ray.init(
            address="local",
            num_cpus=RAY_CPUS,
            num_gpus=1,
            include_dashboard=False,
            _temp_dir=str(args.ray_temp_dir),
            _memory=args.ray_memory_gib * GIB,
            object_store_memory=args.object_store_gib * GIB,
            runtime_env={"env_vars": env},
        )
        ray_started = True
        cluster = ray.cluster_resources()
        if cluster.get("CPU") != RAY_CPUS or cluster.get("GPU") != 1:
            raise RuntimeError(f"unexpected Ray resources: {cluster}")
        for key, expected in (
            ("memory", args.ray_memory_gib * GIB),
            ("object_store_memory", args.object_store_gib * GIB),
        ):
            if abs(cluster.get(key, 0) - expected) > 16 * 1024 ** 2:
                raise RuntimeError(f"Ray did not respect {key} limit")

        probe_actor = ray.remote(num_cpus=0)(common.node_probe)
        probe = ray.get(
            probe_actor.remote(configuration["problem"], args.dimension),
            timeout=args.operation_timeout_seconds,
        )
        if (
            probe["runtime_sha256"] != manifest["runtime_sha256"]
            or probe["versions"]
            != {name: versions[name] for name in ("numpy", "jmetalpy", "ray", "scikit-learn")}
            or probe["benchmark"] != benchmark_metadata
        ):
            raise RuntimeError("worker runtime, dependencies or benchmark differ from driver")

        GpuEvaluator = make_gpu_evaluator()
        MigrationRouter = make_router()
        EvaluationBatcher = make_batcher()
        IslandShard = make_island_shard()
        gpu = GpuEvaluator.remote(max_batch_rows=batching["max_rows"])
        router = MigrationRouter.remote(args.islands)
        batcher = EvaluationBatcher.remote(
            gpu,
            initial_target_rows=batching["initial_target_rows"],
            steady_target_rows=batching["steady_target_rows"],
            max_rows=batching["max_rows"],
            initial_max_wait_ms=batching["initial_max_wait_ms"],
            steady_max_wait_ms=batching["steady_max_wait_ms"],
        )
        run_params = asdict(params)
        shards = [
            IslandShard.remote(
                shard_id=item["shard_id"],
                island_ids=item["island_ids"],
                adjacency=adjacency,
                run_params=run_params,
                run_id=run_id,
                problem_id=args.problem,
                dimension=args.dimension,
                instance_seed=args.instance_seed,
                batcher=batcher,
                router=router,
                package_root=str(PACKAGE_ROOT),
                operation_timeout_seconds=args.operation_timeout_seconds,
            )
            for item in plan["shards"]
        ]
        gpu_before = ray.get(gpu.environment.remote(), timeout=args.operation_timeout_seconds)
        island_zero = ray.get(
            shards[0].prepare_island_zero.remote(),
            timeout=args.actor_startup_timeout,
        )
        if Path(island_zero["run_directory"]).resolve() != raw:
            raise RuntimeError("island 0 created a different run directory than the driver")
        if island_zero["benchmark"] != benchmark_metadata:
            raise RuntimeError("sharded builder benchmark differs from driver preflight")
        placements = ray.get(
            [shard.prepare_remaining.remote() for shard in shards],
            timeout=args.actor_startup_timeout,
        )
        initialized = ray.get(
            [shard.initialize.remote() for shard in shards],
            timeout=args.actor_startup_timeout,
        )
        if sum(len(item["initialized_islands"]) for item in initialized) != args.islands:
            raise RuntimeError("not every logical island initialized")
        manifest.update(
            {
                "status": "running",
                "node_checks": [probe],
                "ray_resources": cluster,
                "gpu_before": gpu_before,
                "shard_placements": placements,
            }
        )
        run_metadata.update(
            {
                "status": "running",
                "ray_resources": cluster,
                "shard_placements": placements,
            }
        )
        common.dump(audit / "experiment_manifest.json", manifest)
        common.dump(audit / "run_metadata.json", run_metadata)

        shard_runs = ray.get(
            [shard.run.remote() for shard in shards],
            timeout=args.run_timeout_seconds,
        )
        batch_summary = ray.get(
            batcher.flush.remote(),
            timeout=args.operation_timeout_seconds,
        )
        ray.get(
            [shard.acknowledge_deliveries.remote() for shard in shards],
            timeout=args.operation_timeout_seconds,
        )
        nested_results = ray.get(
            [shard.finalize.remote() for shard in shards],
            timeout=args.finalization_timeout_seconds,
        )
        results = sorted(
            [item for group in nested_results for item in group],
            key=lambda item: item["island"],
        )
        athena_metrics = raw / "metrics" / "athena"
        exported_summary = ray.get(
            batcher.export_metrics.remote(str(athena_metrics)),
            timeout=args.finalization_timeout_seconds,
        )
        if exported_summary != batch_summary:
            raise RuntimeError("batcher summary changed between flush and export")
        gpu_after = ray.get(gpu.environment.remote(), timeout=args.operation_timeout_seconds)
        router_summary = ray.get(router.summary.remote(), timeout=args.operation_timeout_seconds)
        _write_athena_contract(
            athena_metrics,
            plan=plan,
            backend={"before": gpu_before, "after": gpu_after},
            shards=placements,
            router=router_summary,
        )
        _basic_output_check(raw, args, results, batch_summary)
        common.dump(raw / "iterations_per_second.json", {str(item["island"]): item for item in results})
        common.save_topology(audit, args, adjacency)
        benchmark_run_metadata = json.loads(
            (raw / "benchmark_manifest.json").read_text(encoding="utf-8")
        )
        completed = datetime.now(timezone.utc).isoformat()
        manifest.update(
            {
                "status": "complete",
                "completed_utc": completed,
                "islands_completed": len(results),
                "gpu_after": gpu_after,
                "batch_summary": batch_summary,
                "migration_router_summary": router_summary,
                "shard_runs": shard_runs,
            }
        )
        run_metadata.update(
            {
                "status": "complete",
                "completed_utc": completed,
                "islands_completed": len(results),
                "active_operators": benchmark_run_metadata.get("active_operators"),
                "athena_batch_summary": batch_summary,
                "migration_router_summary": router_summary,
            }
        )
        print(f"ATHENA_STUDY_RUN_OK={raw}", flush=True)
    except BaseException as error:
        manifest.update({"status": "failed", "error": repr(error)})
        run_metadata.update(
            {
                "status": "failed",
                "failed_utc": datetime.now(timezone.utc).isoformat(),
                "error": repr(error),
            }
        )
        raise
    finally:
        common.dump(audit / "experiment_manifest.json", manifest)
        common.dump(audit / "run_metadata.json", run_metadata)
        if raw.is_dir():
            for name in (
                "experiment_manifest.json",
                "run_metadata.json",
                "topology.json",
                "topology.png",
            ):
                source = audit / name
                if source.exists():
                    shutil.copy2(source, raw / name)
        if args.result_pointer:
            pointer = Path(args.result_pointer).resolve()
            pointer.parent.mkdir(parents=True, exist_ok=True)
            common.dump(
                pointer,
                {
                    "schema_version": 2,
                    "status": manifest["status"],
                    "run_id": run_id,
                    "experiment_key": experiment_key,
                    "run_directory": str(raw),
                    "audit_directory": str(audit),
                    "experiment_manifest": str(audit / "experiment_manifest.json"),
                    "run_metadata": str(audit / "run_metadata.json"),
                },
            )
        if ray_started:
            ray.shutdown()


if __name__ == "__main__":
    run(parser().parse_args())
