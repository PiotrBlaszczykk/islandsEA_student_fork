#!/usr/bin/env python3
"""Plan, audit and finalize fixed torus 40x3 Ares selection campaigns."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import tarfile
import zlib


STRATEGY = os.environ.get("ISLANDS_CAMPAIGN_STRATEGY", "best")
if STRATEGY not in ("best", "random", "maxDistance"):
    raise ValueError(f"unsupported torus campaign strategy: {STRATEGY}")
CAMPAIGN_SLUG = STRATEGY.lower()
SCHEMA = f"islandsea-torus-{CAMPAIGN_SLUG}-campaign-v1"
CAMPAIGN = f"torus_{CAMPAIGN_SLUG}"
BASE_SEED = 20260912
DIMENSION = 200
REPEATS = (1, 2, 3)
CONTINUOUS = (
    "r01_elliptic", "r02_bent_cigar", "r03_discus", "r04_rosenbrock",
    "r05_ackley", "r06_weierstrass", "r07_griewank", "r08_rastrigin",
    "r09_rot_rastrigin", "r10_schwefel", "r11_rot_schwefel", "r12_katsuura",
    "r13_happycat", "r14_hgbat", "r15_grie_rosen", "r16_schaffer_f6",
    "r17_hybrid1", "r18_hybrid2", "r19_hybrid3", "r20_hybrid4",
    "r21_hybrid5", "r22_hybrid6", "r23_composition1", "r24_composition2",
    "r25_composition3", "r26_composition4", "r27_composition5",
    "r28_composition6", "r29_composition7", "r30_composition8",
)
BINARY = (
    "b01_labs_binary", "b02_trap5", "b03_nk_k4", "b04_onemax",
    "b05_zeromax", "b06_leading_ones", "b07_alternating_bits",
    "b08_trap4", "b09_royal_road4", "b10_maxcut_ring",
)
BENCHMARKS = CONTINUOUS + BINARY
CONFIGURATION = {
    "dimension": DIMENSION,
    "islands": 144,
    "evaluations_per_island": 8000,
    "population": 16,
    "offspring": 4,
    "migration": {
        "group_size": 5,
        "interval": 5,
        "interval_unit": "evaluation-count difference",
        "selection": STRATEGY,
        "acceptance": "plain",
    },
    "topology": {"name": "torus", "rows": 12, "columns": 12},
    "metrics_profile": "research-v1-full-buffered",
    "base_seed": BASE_SEED,
}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"), parse_constant=reject_nonfinite)


def reject_nonfinite(value):
    raise ValueError(f"non-finite JSON value: {value}")


def task_matrix():
    tasks = []
    for benchmark in BENCHMARKS:
        for repeat in REPEATS:
            tasks.append({
                "task_id": len(tasks) + 1,
                "benchmark": benchmark,
                "family": "continuous" if benchmark.startswith("r") else "binary",
                "dimension": DIMENSION,
                "repeat": repeat,
                "repeat_seed": BASE_SEED + (repeat - 1) * 1_000_000,
            })
    return tasks


def expected_plan(git_commit):
    return {
        "schema": SCHEMA,
        "campaign": CAMPAIGN,
        "created_utc": utc_now(),
        "git_commit_at_submission": git_commit,
        "configuration": CONFIGURATION,
        "benchmark_count": len(BENCHMARKS),
        "repeat_count": len(REPEATS),
        "task_count": len(BENCHMARKS) * len(REPEATS),
        "tasks": task_matrix(),
    }


def validate_plan(plan):
    if plan.get("schema") != SCHEMA or plan.get("campaign") != CAMPAIGN:
        raise ValueError("invalid campaign plan identity")
    if plan.get("configuration") != CONFIGURATION:
        raise ValueError("campaign configuration differs from the frozen contract")
    if plan.get("tasks") != task_matrix() or plan.get("task_count") != 120:
        raise ValueError("campaign plan must contain the exact 40 x 3 task matrix")
    commit = plan.get("git_commit_at_submission")
    if not isinstance(commit, str) or len(commit) != 40:
        raise ValueError("campaign plan has no full Git commit")
    return plan


def load_plan(path):
    return validate_plan(read_json(path))


def task_for(plan, task_id):
    if isinstance(task_id, bool) or not isinstance(task_id, int) or not 1 <= task_id <= 120:
        raise ValueError("task id must be in 1..120")
    task = plan["tasks"][task_id - 1]
    if task["task_id"] != task_id:
        raise ValueError("task index mismatch in campaign plan")
    return task


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_metadata(metadata, task, array_job_id, job_id):
    errors = []

    def require(condition, message):
        if not condition:
            errors.append(message)

    config = metadata.get("scientific_configuration", {})
    benchmark = config.get("benchmark", {})
    migration = config.get("migration", {})
    topology = config.get("topology", {})
    parameters = topology.get("parameters", {})
    seed = config.get("seed", {})
    metrics = config.get("metrics", {})
    slurm = metadata.get("resources", {}).get("slurm", {})
    require(metadata.get("status") == "complete", "scientific status is not complete")
    require(bool(metadata.get("run_id")), "run_id is missing")
    require(bool(metadata.get("experiment_key")), "experiment_key is missing")
    require(benchmark.get("name") == task["benchmark"], "benchmark mismatch")
    require(config.get("dimension") == DIMENSION, "dimension mismatch")
    require(config.get("islands") == 144, "island count mismatch")
    require(config.get("evaluations_per_island") == 8000, "evaluation budget mismatch")
    require(config.get("population") == 16, "population mismatch")
    require(config.get("offspring") == 4, "offspring mismatch")
    require(config.get("repeat") == task["repeat"], "repeat mismatch")
    require(migration.get("group_size") == 5, "migrant count mismatch")
    require(migration.get("interval") == 5, "migration interval mismatch")
    require(migration.get("interval_unit") == "evaluation-count difference", "migration interval unit mismatch")
    require(migration.get("selection") == STRATEGY, "migration selection mismatch")
    require(migration.get("acceptance") == "plain", "migration acceptance mismatch")
    require(topology.get("name") == "torus", "topology mismatch")
    require(parameters.get("rows") == 12 and parameters.get("columns") == 12, "torus shape mismatch")
    require(seed.get("requested_base") == BASE_SEED, "base seed mismatch")
    require(seed.get("repeat_base") == task["repeat_seed"], "repeat seed mismatch")
    require(metrics.get("profile") == "research-v1-full-buffered", "metrics profile mismatch")
    require(str(slurm.get("SLURM_JOB_ID")) == str(job_id), "SLURM job id mismatch")
    require(str(slurm.get("SLURM_ARRAY_JOB_ID")) == str(array_job_id), "SLURM array id mismatch")
    require(str(slurm.get("SLURM_ARRAY_TASK_ID")) == str(task["task_id"]), "SLURM task id mismatch")
    require(str(slurm.get("SLURM_JOB_NUM_NODES")) == "7", "node count mismatch")
    require(slurm.get("SLURM_JOB_ACCOUNT") == "plglscclass26-cpu", "SLURM account mismatch")
    require(slurm.get("SLURM_JOB_PARTITION") == "plgrid", "SLURM partition mismatch")
    require(str(slurm.get("ISLANDS_ALLOCATED_CPUS_PER_NODE")) == "48", "CPU profile mismatch")
    require(metadata.get("resources", {}).get("required_ray_cpus") == 289, "Ray CPU demand mismatch")
    require(metadata.get("resources", {}).get("required_slurm_cpus") == 290, "SLURM CPU demand mismatch")
    require(metadata.get("provenance", {}).get("git_dirty") is False, "run used a dirty checkout")
    return errors


def validate_run(campaign_dir, plan_path, task_id, array_job_id, job_id,
                 execution_array_job_id=None):
    """Validate one completed scientific run before its portable export."""
    campaign = Path(campaign_dir).resolve()
    plan = load_plan(plan_path)
    task = task_for(plan, task_id)
    task_dir = campaign / "tasks" / f"task-{task_id:03d}"
    errors = []
    execution_array_job_id = str(execution_array_job_id or array_job_id)
    result = {
        "schema": SCHEMA, "campaign": CAMPAIGN, "mode": "full",
        "task_id": task_id, "benchmark": task["benchmark"],
        "repeat": task["repeat"], "job_id": str(job_id),
        "array_job_id": str(array_job_id), "checked_utc": utc_now(),
        "execution_array_job_id": execution_array_job_id,
        "valid": False, "errors": errors,
    }

    def require(condition, message):
        if not condition:
            errors.append(message)

    def json_file(path):
        try:
            return read_json(path)
        except (OSError, ValueError) as error:
            errors.append(f"cannot read {path.name}: {error}")
            return {}

    def stream_records(path):
        try:
            with gzip.open(path, "rt", encoding="utf-8") as stream:
                for number, line in enumerate(stream, 1):
                    record = json.loads(line, parse_constant=reject_nonfinite)
                    if not isinstance(record, dict):
                        raise ValueError(f"line {number} is not an object")
                    yield record
        except (OSError, EOFError, UnicodeError, ValueError, zlib.error) as error:
            errors.append(f"invalid stream {path}: {error}")

    pointer_path = task_dir / "result_pointer.json"
    pointer = json_file(pointer_path)
    require(pointer.get("status") == "complete", "result pointer is not complete")
    raw_name = pointer.get("run_directory")
    raw = Path(raw_name).resolve() if isinstance(raw_name, str) and raw_name else None
    expected_raw_root = campaign / "storage" / "results" / "runs"
    if raw is None or not raw.is_relative_to(expected_raw_root) or not raw.is_dir():
        errors.append("raw run directory is missing or outside this campaign")
    else:
        metadata = json_file(raw / "run_metadata.json")
        errors.extend(validate_metadata(metadata, task, execution_array_job_id, job_id))
        result["run_id"] = metadata.get("run_id")
        result["experiment_key"] = metadata.get("experiment_key")
        require(pointer.get("run_id") == metadata.get("run_id"), "pointer run_id mismatch")
        manifest = json_file(raw / "experiment_manifest.json")
        benchmark = json_file(raw / "benchmark_manifest.json")
        topology = json_file(raw / "topology.json")
        require(manifest.get("status") == "complete", "experiment manifest is not complete")
        require(manifest.get("islands_completed") == 144, "experiment did not complete 144 islands")
        require(benchmark.get("name") == task["benchmark"], "benchmark manifest name mismatch")
        require(benchmark.get("dimension") == DIMENSION, "benchmark manifest dimension mismatch")
        require(topology.get("name") == "torus", "topology file name mismatch")
        require(topology.get("islands") == 144, "topology file island count mismatch")
        require(topology.get("torus_shape", {}).get("rows") == 12, "topology rows mismatch")
        require(topology.get("torus_shape", {}).get("columns") == 12, "topology columns mismatch")
        require(
            topology.get("graph_metrics", {}).get("adjacency_sha256")
            == metadata.get("scientific_configuration", {}).get("topology", {}).get("adjacency_sha256"),
            "topology adjacency hash mismatch",
        )
        contract = json_file(raw / "metrics" / "data_contract.json")
        require(contract.get("schema_version") == 1, "metrics data contract is missing")
        run_id = metadata.get("run_id")
        sent_ids, processed_ids = set(), set()
        sent_count = processed_count = 0
        duplicate_sent = duplicate_processed = 0
        final_count = 0
        final_objectives = []
        for island in range(144):
            directory = raw / "metrics" / f"island_{island:03d}"
            summary = json_file(directory / "summary.json")
            runtime = json_file(directory / "runtime.json")
            final = json_file(directory / "final_solution.json")
            require(summary.get("run_id") == run_id and summary.get("island") == island,
                    f"island {island}: summary identity mismatch")
            require(runtime.get("island") == island, f"island {island}: runtime identity mismatch")
            require(runtime.get("actual_evaluations") == 8000, f"island {island}: evaluation count mismatch")
            require(runtime.get("actual_steps") == 1996, f"island {island}: step count mismatch")
            require(summary.get("fitness_snapshot_records") == 1997,
                    f"island {island}: fitness snapshot count mismatch")
            require(summary.get("queue_fetch_records") == 1997,
                    f"island {island}: queue fetch count mismatch")
            variables = final.get("variables")
            objectives = final.get("objectives")
            good_final = (
                final.get("run_id") == run_id and final.get("island") == island
                and final.get("variable_count") == DIMENSION
                and isinstance(variables, list) and len(variables) == DIMENSION
                and isinstance(objectives, list) and len(objectives) == 1
                and isinstance(objectives[0], (int, float)) and math.isfinite(objectives[0])
            )
            require(good_final, f"island {island}: invalid final solution")
            if good_final:
                try:
                    canonical = json.dumps(variables, separators=(",", ":"), allow_nan=False).encode("utf-8")
                except (TypeError, ValueError) as error:
                    errors.append(f"island {island}: invalid genotype values: {error}")
                else:
                    expected_hash = hashlib.sha256(canonical).hexdigest()
                    require(final.get("variables_sha256") == expected_hash,
                            f"island {island}: final genotype hash mismatch")
                    require(summary.get("final_solution_variables_sha256") == expected_hash,
                            f"island {island}: summary/final genotype mismatch")
                    final_count += 1
                    final_objectives.append(float(objectives[0]))

            observed = Counter()
            for name, summary_field, kind in (
                ("migration_events.jsonl.gz", None, "events"),
                ("queue_fetches.jsonl.gz", "queue_fetch_records", "queue"),
                ("fitness_history.jsonl.gz", "fitness_snapshot_records", "fitness"),
            ):
                count = 0
                for record in stream_records(directory / name):
                    count += 1
                    if kind == "events":
                        record_type = record.get("record_type")
                        event_id = record.get("event_id")
                        if record.get("run_id") != run_id or record.get("recording_island") != island:
                            errors.append(f"island {island}: migration record identity mismatch")
                        if not isinstance(event_id, str) or not event_id:
                            errors.append(f"island {island}: migration event id is missing")
                        if record_type == "send":
                            sent_count += 1
                            if event_id in sent_ids:
                                duplicate_sent += 1
                            sent_ids.add(event_id)
                        elif record_type == "process":
                            processed_count += 1
                            if event_id in processed_ids:
                                duplicate_processed += 1
                            processed_ids.add(event_id)
                        elif record_type != "local_duplicate":
                            errors.append(f"island {island}: unknown event record type")
                        observed[record_type] += 1
                if summary_field is not None:
                    require(count == summary.get(summary_field),
                            f"island {island}: {name} count differs from summary")
            require(observed["send"] == summary.get("sent_event_records"),
                    f"island {island}: sent count differs from summary")
            require(observed["process"] == summary.get("process_event_records"),
                    f"island {island}: process count differs from summary")
            require(observed["local_duplicate"] == summary.get("local_duplicate_records"),
                    f"island {island}: duplicate count differs from summary")

        require(final_count == 144, "not every island has a valid final solution")
        require(sent_count == processed_count and sent_ids == processed_ids,
                "send/process migration event conservation failed")
        require(duplicate_sent == 0 and duplicate_processed == 0,
                "duplicate migration event ids found")
        result["scientific_counts"] = {
            "islands": final_count, "sent": sent_count, "process": processed_count,
            "duplicate_sent": duplicate_sent, "duplicate_process": duplicate_processed,
        }
        if final_objectives:
            result["final_fitness"] = {
                "best": min(final_objectives),
                "mean": sum(final_objectives) / len(final_objectives),
                "worst": max(final_objectives),
            }

    result["valid"] = not errors
    write_json(task_dir / "validation.json", result)
    print(f"CAMPAIGN_VALIDATION={'OK' if result['valid'] else 'FAILED'} task={task_id} errors={len(errors)}")
    if errors:
        for error in errors[:30]:
            print(f"CAMPAIGN_VALIDATION_ERROR={error}")
        raise ValueError(f"task {task_id} failed validation; see {task_dir / 'validation.json'}")
    return result


def record_task(args):
    plan = load_plan(args.plan)
    task = task_for(plan, args.task_id)
    campaign = Path(args.campaign_dir).resolve()
    path = campaign / "tasks" / f"task-{args.task_id:03d}" / "task.json"
    previous = read_json(path) if path.is_file() else {}
    value = {
        **previous,
        **task,
        "schema": SCHEMA,
        "campaign": CAMPAIGN,
        "array_job_id": str(args.array_job_id),
        "execution_array_job_id": str(args.execution_array_job_id or args.array_job_id),
        "job_id": str(args.job_id),
        "status": args.status,
        "exit_code": args.exit_code,
    }
    if args.status == "running":
        value["started_utc"] = utc_now()
        value.pop("finished_utc", None)
        value.pop("archive", None)
        value.pop("verification", None)
    if args.status in ("completed", "failed"):
        value["finished_utc"] = utc_now()
    if args.archive:
        value["archive"] = str(Path(args.archive).resolve())
    if args.verification:
        value["verification"] = str(Path(args.verification).resolve())
    write_json(path, value)
    print(f"TASK_RECORD={path}")


def finalize(campaign_dir, array_job_id):
    campaign = Path(campaign_dir).resolve()
    plan_path = campaign / "campaign_plan.json"
    plan = load_plan(plan_path)
    errors, entries, run_ids = [], [], set()
    keys_by_benchmark = {}
    runtime_hashes, benchmark_code_hashes, topology_hashes = set(), set(), set()
    total_archive_bytes = 0

    for task in plan["tasks"]:
        task_id = task["task_id"]
        record_path = campaign / "tasks" / f"task-{task_id:03d}" / "task.json"
        prefix = f"task {task_id:03d} ({task['benchmark']}, repeat {task['repeat']})"
        if not record_path.is_file():
            errors.append(f"{prefix}: task record missing")
            continue
        record = read_json(record_path)
        job_id = str(record.get("job_id", ""))
        execution_array_job_id = str(record.get("execution_array_job_id", record.get("array_job_id", "")))
        if record.get("status") != "completed" or record.get("exit_code") != 0:
            errors.append(f"{prefix}: status={record.get('status')} exit={record.get('exit_code')}")
            continue
        if str(record.get("array_job_id")) != str(array_job_id):
            errors.append(f"{prefix}: array job id mismatch")
            continue
        archive = campaign / "runs" / f"run_{job_id}.tar.gz"
        checksum = archive.with_name(archive.name + ".sha256")
        exported = campaign / "runs" / f"run_{job_id}"
        metadata_path = exported / "metadata.json"
        task_dir = campaign / "tasks" / f"task-{task_id:03d}"
        verification_path = task_dir / "bundle_verification.json"
        validation_path = task_dir / "validation.json"
        expected_archive = str(archive.resolve())
        if record.get("archive") != expected_archive:
            errors.append(f"{prefix}: recorded archive path mismatch")
            continue
        if not all(path.is_file() for path in (archive, checksum, metadata_path, verification_path, validation_path)):
            errors.append(f"{prefix}: archive/checksum/metadata/verification/validation is missing")
            continue
        verification = read_json(verification_path)
        validation = read_json(validation_path)
        if not (validation.get("valid") is True and not validation.get("errors")
                and validation.get("task_id") == task_id
                and str(validation.get("job_id")) == job_id
                and str(validation.get("array_job_id")) == str(array_job_id)
                and str(validation.get("execution_array_job_id", execution_array_job_id)) == execution_array_job_id):
            errors.append(f"{prefix}: scientific validation did not pass")
            continue
        if not (verification.get("verified") is True and verification.get("complete") is True
                and verification.get("validation") == "passed"
                and str(verification.get("job_id")) == job_id):
            errors.append(f"{prefix}: worker bundle verification did not pass")
            continue
        checksum_fields = checksum.read_text(encoding="ascii").split()
        digest = sha256(archive)
        if checksum_fields != [digest, archive.name]:
            errors.append(f"{prefix}: archive SHA-256 mismatch")
            continue
        metadata = read_json(metadata_path)
        metadata_errors = validate_metadata(metadata, task, execution_array_job_id, job_id)
        if metadata_errors:
            errors.extend(f"{prefix}: {message}" for message in metadata_errors)
            continue
        run_id = metadata["run_id"]
        if run_id in run_ids:
            errors.append(f"{prefix}: duplicate run_id {run_id}")
            continue
        run_ids.add(run_id)
        keys_by_benchmark.setdefault(task["benchmark"], set()).add(metadata["experiment_key"])
        runtime_hashes.add(metadata.get("provenance", {}).get("runtime_sha256"))
        benchmark_code_hashes.add(metadata.get("scientific_configuration", {}).get("benchmark", {}).get("implementation_sha256"))
        topology_hashes.add(metadata.get("scientific_configuration", {}).get("topology", {}).get("adjacency_sha256"))
        total_archive_bytes += archive.stat().st_size
        entries.append({
            **task,
            "job_id": job_id,
            "execution_array_job_id": execution_array_job_id,
            "run_id": run_id,
            "experiment_key": metadata["experiment_key"],
            "archive": f"runs/{task['benchmark']}/repeat-{task['repeat']}/{archive.name}",
            "archive_bytes": archive.stat().st_size,
            "archive_sha256": digest,
            "bundle_files": verification.get("files"),
            "scientific_counts": validation.get("scientific_counts"),
            "final_fitness": validation.get("final_fitness"),
        })

    for benchmark in BENCHMARKS:
        keys = keys_by_benchmark.get(benchmark, set())
        if len(keys) != 1:
            errors.append(f"{benchmark}: expected one experiment_key across three repeats, got {len(keys)}")
    for label, hashes in (("runtime", runtime_hashes), ("benchmark code", benchmark_code_hashes),
                          ("torus adjacency", topology_hashes)):
        if len(hashes) != 1 or not next(iter(hashes), None):
            errors.append(f"expected one nonempty {label} hash across all 120 runs")
    if len(entries) != 120:
        errors.append(f"expected 120 valid runs, got {len(entries)}")

    summary = {
        "schema": SCHEMA,
        "campaign": CAMPAIGN,
        "checked_utc": utc_now(),
        "array_job_id": str(array_job_id),
        "valid": not errors,
        "errors": errors,
        "expected_runs": 120,
        "valid_runs": len(entries),
        "benchmark_count": len({entry["benchmark"] for entry in entries}),
        "unique_run_ids": len(run_ids),
        "runtime_sha256": next(iter(runtime_hashes)) if len(runtime_hashes) == 1 else None,
        "benchmark_implementation_sha256": next(iter(benchmark_code_hashes)) if len(benchmark_code_hashes) == 1 else None,
        "topology_adjacency_sha256": next(iter(topology_hashes)) if len(topology_hashes) == 1 else None,
        "total_nested_archive_bytes": total_archive_bytes,
        "runs": entries,
    }
    summary_path = campaign / "campaign_summary.json"
    write_json(summary_path, summary)
    if errors:
        raise ValueError(f"campaign validation failed with {len(errors)} error(s); see {summary_path}")

    archive = campaign / f"{CAMPAIGN}.tar.gz"
    checksum = archive.with_name(archive.name + ".sha256")
    if archive.exists() or checksum.exists():
        raise FileExistsError(f"final archive already exists: {archive}")
    temporary = campaign / f".{archive.name}.{os.getpid()}.tmp"
    try:
        with tarfile.open(temporary, "w:gz", compresslevel=1) as stream:
            stream.add(plan_path, arcname=f"{CAMPAIGN}/campaign_plan.json")
            stream.add(summary_path, arcname=f"{CAMPAIGN}/campaign_summary.json")
            for optional in (campaign / "submission.json", campaign / "sacct.txt"):
                if optional.is_file():
                    stream.add(optional, arcname=f"{CAMPAIGN}/{optional.name}")
            for source in sorted((campaign / "logs").glob("*")):
                if source.is_file() and not source.is_symlink():
                    stream.add(source, arcname=f"{CAMPAIGN}/logs/{source.name}")
            for task in plan["tasks"]:
                task_id = task["task_id"]
                source = campaign / "tasks" / f"task-{task_id:03d}" / "task.json"
                stream.add(source, arcname=f"{CAMPAIGN}/task_records/task-{task_id:03d}.json")
            for entry in entries:
                source = campaign / "runs" / f"run_{entry['job_id']}.tar.gz"
                stream.add(source, arcname=f"{CAMPAIGN}/{entry['archive']}")
                stream.add(source.with_name(source.name + ".sha256"),
                           arcname=f"{CAMPAIGN}/{entry['archive']}.sha256")
        os.replace(temporary, archive)
    finally:
        if temporary.exists():
            temporary.unlink()
    digest = sha256(archive)
    checksum.write_text(f"{digest}  {archive.name}\n", encoding="ascii")
    marker = f"TORUS_{STRATEGY.upper()}"
    print(f"{marker}_VALID_RUNS={len(entries)}")
    print(f"{marker}_SUMMARY={summary_path}")
    print(f"{marker}_ARCHIVE={archive}")
    print(f"{marker}_SHA256={checksum}")


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create-plan")
    create.add_argument("--output", type=Path, required=True)
    create.add_argument("--git-commit", required=True)
    task = commands.add_parser("task")
    task.add_argument("--plan", type=Path, required=True)
    task.add_argument("--task-id", type=int, required=True)
    record = commands.add_parser("record-task")
    record.add_argument("--plan", type=Path, required=True)
    record.add_argument("--campaign-dir", type=Path, required=True)
    record.add_argument("--task-id", type=int, required=True)
    record.add_argument("--status", choices=("running", "completed", "failed"), required=True)
    record.add_argument("--job-id", required=True)
    record.add_argument("--array-job-id", required=True)
    record.add_argument("--execution-array-job-id")
    record.add_argument("--exit-code", type=int, required=True)
    record.add_argument("--archive")
    record.add_argument("--verification")
    check = commands.add_parser("validate-run")
    check.add_argument("--plan", type=Path, required=True)
    check.add_argument("--campaign-dir", type=Path, required=True)
    check.add_argument("--task-id", type=int, required=True)
    check.add_argument("--job-id", required=True)
    check.add_argument("--array-job-id", required=True)
    check.add_argument("--execution-array-job-id")
    submission = commands.add_parser("record-submission")
    submission.add_argument("--plan", type=Path, required=True)
    submission.add_argument("--output", type=Path, required=True)
    submission.add_argument("--array-job-id", required=True)
    submission.add_argument("--finalizer-job-id", required=True)
    submission.add_argument("--max-parallel", type=int, required=True)
    final = commands.add_parser("finalize")
    final.add_argument("--campaign-dir", type=Path, required=True)
    final.add_argument("--array-job-id", required=True)
    return result


def main():
    args = parser().parse_args()
    if args.command == "create-plan":
        write_json(args.output, expected_plan(args.git_commit))
        print(f"CAMPAIGN_PLAN={args.output}")
    elif args.command == "task":
        task = task_for(load_plan(args.plan), args.task_id)
        print(task["benchmark"])
        print(task["dimension"])
        print(task["repeat"])
    elif args.command == "record-task":
        record_task(args)
    elif args.command == "validate-run":
        validate_run(args.campaign_dir, args.plan, args.task_id, args.array_job_id,
                     args.job_id, args.execution_array_job_id)
    elif args.command == "record-submission":
        plan = load_plan(args.plan)
        write_json(args.output, {
            "schema": SCHEMA,
            "campaign": CAMPAIGN,
            "submitted_utc": utc_now(),
            "git_commit": plan["git_commit_at_submission"],
            "array_job_id": str(args.array_job_id),
            "finalizer_job_id": str(args.finalizer_job_id),
            "max_parallel": args.max_parallel,
            "array": "1-120",
        })
        print(f"CAMPAIGN_SUBMISSION={args.output}")
    else:
        finalize(args.campaign_dir, args.array_job_id)


if __name__ == "__main__":
    main()
