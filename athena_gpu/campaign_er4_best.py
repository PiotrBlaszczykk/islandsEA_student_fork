#!/usr/bin/env python3
"""Index ER4/best or ER4/random arrays without changing per-run bundles."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "islands_desync"))

from athena_gpu.production_er4_best import BENCHMARKS, REPEATS, TASK_COUNT, check_contract, configuration
from hpc_benchmarks.run_bundle import verify_archive
from islands_desync.islands.topologies.fixed_graph import graph_parameters, load_graph


SCHEMA = "islandsea-er4-best-athena-campaign-v1"
BASE_SEED = 20260912
INSTANCE_SEED = 20260511
DIMENSION = 200


def er4_campaign_name(strategy: str) -> str:
    if strategy not in ("best", "random"):
        raise ValueError(f"Unsupported ER4 production strategy: {strategy}")
    return f"er4_{strategy}"


def campaign_schema(strategy: str) -> str:
    return f"islandsea-{er4_campaign_name(strategy).replace('_', '-')}-athena-campaign-v1"


def task_matrix() -> list[dict]:
    return [
        {
            "task_id": task_id,
            "benchmark": configuration(task_id)[0],
            "family": "continuous" if configuration(task_id)[0].startswith("r") else "binary",
            "dimension": DIMENSION,
            "repeat": configuration(task_id)[1],
            "repeat_seed": BASE_SEED + (configuration(task_id)[1] - 1) * 1_000_000,
        }
        for task_id in range(1, TASK_COUNT + 1)
    ]


def plan_document(array_job_id: str, git_commit: str, strategy: str = "best") -> dict:
    name = er4_campaign_name(strategy)
    check_contract()
    graph = load_graph("er4")
    return {
        "schema": campaign_schema(strategy),
        "campaign": name,
        "array_job_id": array_job_id,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit_at_submission": git_commit,
        "configuration": {
            "dimension": DIMENSION,
            "islands": 144,
            "evaluations_per_island": 8000,
            "population": 16,
            "offspring": 4,
            "migration": {
                "group_size": 5,
                "interval": 5,
                "interval_unit": "evaluation-count difference",
                "selection": strategy,
                "acceptance": "plain",
            },
            "topology": {
                "name": "er4",
                "parameters": graph_parameters("er4"),
                "adjacency_sha256": graph["provenance"]["adjacency_sha256"],
            },
            "metrics_profile": "research-v1-full-buffered",
            "base_seed": BASE_SEED,
            "benchmark_instance_seed": INSTANCE_SEED,
        },
        "benchmark_count": len(BENCHMARKS),
        "repeat_count": len(REPEATS),
        "task_count": TASK_COUNT,
        "tasks": task_matrix(),
    }


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_exclusive(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as target:
        json.dump(value, target, indent=2, ensure_ascii=False, allow_nan=False)
        target.write("\n")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_regular_file(path: Path, label: str) -> None:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"{label} is missing or not a regular file: {path}")


def checksum_digest(path: Path, archive_name: str) -> str:
    require_regular_file(path, "checksum")
    fields = path.read_text(encoding="ascii").split()
    if (len(fields) != 2 or fields[1] != archive_name or len(fields[0]) != 64
            or any(character not in "0123456789abcdefABCDEF" for character in fields[0])):
        raise ValueError(f"malformed checksum for {archive_name}: {path}")
    return fields[0].lower()


def validate_plan(plan: dict, array_job_id: str, strategy: str = "best") -> None:
    expected = plan_document(array_job_id, plan.get("git_commit_at_submission", ""), strategy)
    for key in ("schema", "campaign", "array_job_id", "configuration", "benchmark_count", "repeat_count", "task_count", "tasks"):
        if plan.get(key) != expected[key]:
            raise ValueError(f"Campaign plan field {key} differs from the approved 120-task contract")
    commit = plan.get("git_commit_at_submission")
    if (not isinstance(commit, str) or len(commit) != 40 or
            any(character not in "0123456789abcdefABCDEF" for character in commit)):
        raise ValueError("Campaign plan has no full Git commit provenance")


def record_task(campaign_dir: Path, array_job_id: str, task_id: int, job_id: str,
                run_dir: Path, archive: Path, strategy: str = "best") -> dict:
    if not array_job_id.isdecimal() or not job_id.isdecimal():
        raise ValueError("SLURM job IDs must be decimal")
    if campaign_dir.name != f"{er4_campaign_name(strategy)}_{array_job_id}":
        raise ValueError("Campaign directory is not tied to this array ID")
    plan = read_json(campaign_dir / "campaign_plan.json")
    validate_plan(plan, array_job_id, strategy)
    task = plan["tasks"][task_id - 1]
    if task["task_id"] != task_id:
        raise ValueError("Campaign task index mismatch")
    if run_dir.name != job_id or archive.name != f"run_{job_id}.tar.gz":
        raise ValueError("Run directory/archive does not match the actual SLURM job ID")
    validation = read_json(run_dir / "validation.json")
    for key, value in {
        "status": "passed", "valid": True, "mode": "full",
        "benchmark": task["benchmark"], "dimension": DIMENSION,
        "topology": "er4", "migrant_selection": strategy,
        "migrant_acceptance": "plain", "repeat": task["repeat"],
        "base_seed": BASE_SEED, "repeat_seed": task["repeat_seed"],
    }.items():
        if validation.get(key) != value:
            raise ValueError(f"Validation field {key} does not match the campaign task")
    pointer = read_json(run_dir / "result_pointer.json")
    raw = Path(pointer["run_directory"])
    metadata = read_json(raw / "run_metadata.json")
    config = metadata["scientific_configuration"]
    slurm = metadata["resources"]["slurm"]
    run_commit = metadata.get("provenance", {}).get("git_commit")
    if not run_commit or run_commit != validation.get("git_commit"):
        raise ValueError("Run Git provenance differs between validation and metadata")
    expected_config = plan["configuration"]
    for key, value in {
        "dimension": DIMENSION,
        "islands": 144,
        "evaluations_per_island": 8000,
        "population": 16,
        "offspring": 4,
        "repeat": task["repeat"],
    }.items():
        if config.get(key) != value:
            raise ValueError(f"Scientific metadata field {key} differs from campaign plan")
    if config.get("benchmark", {}).get("name") != task["benchmark"]:
        raise ValueError("Scientific benchmark differs from campaign task")
    if config.get("migration") != expected_config["migration"]:
        raise ValueError("Scientific migration differs from campaign plan")
    if config.get("topology") != expected_config["topology"]:
        raise ValueError("Scientific ER4 topology differs from campaign plan")
    seed = config.get("seed") or {}
    for key, value in {
        "requested_base": BASE_SEED,
        "repeat_base": task["repeat_seed"],
        "benchmark_instance_seed": INSTANCE_SEED,
    }.items():
        if seed.get(key) != value:
            raise ValueError(f"Scientific seed field {key} differs from campaign plan")
    if config.get("metrics", {}).get("profile") != "research-v1-full-buffered":
        raise ValueError("Scientific metrics profile differs from campaign plan")
    for key, value in {
        "SLURM_JOB_ID": job_id,
        "SLURM_ARRAY_JOB_ID": array_job_id,
        "SLURM_ARRAY_TASK_ID": str(task_id),
    }.items():
        if str(slurm.get(key)) != value:
            raise ValueError(f"Scientific SLURM field {key} differs from campaign task")
    verified = verify_archive(archive)
    if verified.get("job_id") != job_id or verified.get("complete") is not True or verified.get("validation") != "passed":
        raise ValueError("Portable run bundle is not complete and passed")
    checksum = archive.with_name(archive.name + ".sha256")
    archive_sha256 = checksum_digest(checksum, archive.name)
    if sha256(archive) != archive_sha256:
        raise ValueError("Portable run bundle SHA-256 differs from its checksum")
    relative = Path("runs") / task["benchmark"] / f"repeat-{task['repeat']}"
    destination = campaign_dir / relative
    if destination.exists():
        raise FileExistsError(f"Campaign task archive already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    # A hard link keeps the canonical $SCRATCH/islandsEA/exports/run_<id> files
    # and the one-download campaign tree byte-identical without duplicating 120
    # large archives on the same SCRATCH filesystem.
    with tempfile.TemporaryDirectory(prefix=f".task-{task_id:03d}-", dir=campaign_dir) as temporary:
        staged = Path(temporary) / "bundle"
        staged.mkdir()
        os.link(archive, staged / archive.name)
        os.link(checksum, staged / checksum.name)
        staged.rename(destination)
    record = {
        "schema": campaign_schema(strategy),
        "status": "completed",
        "array_job_id": array_job_id,
        "task_id": task_id,
        "job_id": job_id,
        "benchmark": task["benchmark"],
        "dimension": DIMENSION,
        "repeat": task["repeat"],
        "topology": "er4",
        "migrant_selection": strategy,
        "migrant_acceptance": "plain",
        "archive": (relative / archive.name).as_posix(),
        "archive_sha256": archive_sha256,
        "bundle_complete": True,
        "validation": "passed",
        "git_commit": run_commit,
    }
    write_json_exclusive(campaign_dir / "tasks" / f"task-{task_id:03d}.json", record)
    return record


def read_accounting(path: Path, array_job_id: str) -> dict[int, str]:
    """Require real numeric SLURM job IDs and successful terminal array states."""
    require_regular_file(path, "SLURM accounting")
    jobs: dict[int, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        fields = line.split("|")
        if fields == ["JobIDRaw", "JobID", "State", "ExitCode"]:
            continue
        if len(fields) != 4:
            raise ValueError(f"invalid sacct row: {line}")
        actual_id, array_task, state, exit_code = fields
        if array_task == array_job_id:
            continue  # A possible parent-array accounting row, not a run.
        prefix = f"{array_job_id}_"
        if not array_task.startswith(prefix) or not array_task[len(prefix):].isdecimal():
            raise ValueError(f"unexpected sacct array element: {array_task}")
        task_id = int(array_task[len(prefix):])
        if not 1 <= task_id <= TASK_COUNT or task_id in jobs or not actual_id.isdecimal():
            raise ValueError(f"duplicate or invalid sacct task: {array_task}")
        if state != "COMPLETED" or exit_code != "0:0":
            raise ValueError(f"task {task_id} did not complete successfully: {state} {exit_code}")
        jobs[task_id] = actual_id
    if set(jobs) != set(range(1, TASK_COUNT + 1)):
        raise ValueError(f"sacct has {len(jobs)} of {TASK_COUNT} completed array tasks")
    return jobs


def finalize_campaign(campaign_dir: Path, array_job_id: str, results_root: Path,
                      logs_root: Path, sacct_file: Path, strategy: str = "best") -> dict:
    """Audit only persisted runs, then create one portable, immutable campaign tar."""
    if not array_job_id.isdecimal() or campaign_dir.name != f"{er4_campaign_name(strategy)}_{array_job_id}":
        raise ValueError("campaign directory and array job ID differ")
    campaign_dir = campaign_dir.resolve()
    plan_path = campaign_dir / "campaign_plan.json"
    require_regular_file(plan_path, "campaign plan")
    plan = read_json(plan_path)
    validate_plan(plan, array_job_id, strategy)
    task_dir = campaign_dir / "tasks"
    expected_records = {f"task-{task_id:03d}.json" for task_id in range(1, TASK_COUNT + 1)}
    if (not task_dir.is_dir() or
            {path.name for path in task_dir.iterdir()} != expected_records):
        raise ValueError("campaign must contain exactly the 120 planned task records")
    slurm_jobs = read_accounting(sacct_file, array_job_id)
    campaign_name = campaign_dir.name
    archive = campaign_dir / f"{campaign_name}.tar.gz"
    checksum = campaign_dir / f"{campaign_name}.tar.gz.sha256"
    if archive.exists() or checksum.exists():
        raise FileExistsError("campaign archive/checksum already exists; refusing to overwrite")

    entries = []
    files_to_archive = [
        (plan_path, f"{campaign_name}/campaign_plan.json"),
        (sacct_file, f"{campaign_name}/sacct.txt"),
    ]
    log_names = []
    missing_logs = []
    seen_jobs = set()
    total_bytes = 0
    for task in plan["tasks"]:
        task_id = task["task_id"]
        record_path = task_dir / f"task-{task_id:03d}.json"
        require_regular_file(record_path, f"task {task_id} record")
        record = read_json(record_path)
        job_id = str(record.get("job_id", ""))
        if (not job_id.isdecimal() or job_id in seen_jobs or
                slurm_jobs[task_id] != job_id):
            raise ValueError(f"task {task_id} has a missing, duplicate or wrong real SLURM job ID")
        seen_jobs.add(job_id)
        expected_record = {
            "schema": campaign_schema(strategy), "status": "completed", "array_job_id": array_job_id,
            "task_id": task_id, "job_id": job_id,
            "benchmark": task["benchmark"], "dimension": DIMENSION,
            "repeat": task["repeat"], "topology": "er4",
            "migrant_selection": strategy, "migrant_acceptance": "plain",
            "bundle_complete": True, "validation": "passed",
        }
        for key, value in expected_record.items():
            if record.get(key) != value:
                raise ValueError(f"task {task_id} record field {key} differs from plan")
        run_commit = record.get("git_commit")
        if (not isinstance(run_commit, str) or len(run_commit) != 40 or
                any(character not in "0123456789abcdefABCDEF" for character in run_commit)):
            raise ValueError(f"task {task_id} has invalid Git provenance")
        relative = f"runs/{task['benchmark']}/repeat-{task['repeat']}/run_{job_id}.tar.gz"
        if record.get("archive") != relative:
            raise ValueError(f"task {task_id} archive path differs from plan")
        bundle = campaign_dir / relative
        bundle_checksum = bundle.with_name(bundle.name + ".sha256")
        require_regular_file(bundle, f"task {task_id} bundle")
        digest = checksum_digest(bundle_checksum, bundle.name)
        if digest != str(record.get("archive_sha256", "")).lower() or sha256(bundle) != digest:
            raise ValueError(f"task {task_id} archive SHA-256 mismatch")
        verified = verify_archive(bundle)
        if (verified.get("verified") is not True or verified.get("job_id") != job_id or
                verified.get("complete") is not True or verified.get("validation") != "passed"):
            raise ValueError(f"task {task_id} portable bundle is not complete and passed")

        validation_path = results_root / job_id / "validation.json"
        require_regular_file(validation_path, f"task {task_id} scientific validation")
        validation = read_json(validation_path)
        expected_validation = {
            "status": "passed", "valid": True, "errors": [], "mode": "full",
            "benchmark": task["benchmark"], "dimension": DIMENSION,
            "topology": "er4", "migrant_selection": strategy,
            "migrant_acceptance": "plain", "repeat": task["repeat"],
            "base_seed": BASE_SEED, "repeat_seed": task["repeat_seed"],
            "git_commit": run_commit,
        }
        for key, value in expected_validation.items():
            if validation.get(key) != value:
                raise ValueError(f"task {task_id} scientific validation field {key} failed")
        files_to_archive.extend((
            (record_path, f"{campaign_name}/tasks/{record_path.name}"),
            (validation_path, f"{campaign_name}/validations/task-{task_id:03d}.json"),
            (bundle, f"{campaign_name}/{relative}"),
            (bundle_checksum, f"{campaign_name}/{relative}.sha256"),
        ))
        task_logs = []
        for suffix in ("out", "err"):
            name = f"athena-er4-{strategy}-120-{array_job_id}_{task_id}.{suffix}"
            source = logs_root / name
            if source.is_file() and not source.is_symlink():
                files_to_archive.append((source, f"{campaign_name}/logs/{name}"))
                log_names.append(name)
                task_logs.append(f"logs/{name}")
            else:
                missing_logs.append(name)
        total_bytes += bundle.stat().st_size
        entries.append({
            "task_id": task_id, "job_id": job_id, "benchmark": task["benchmark"],
            "repeat": task["repeat"], "archive": relative,
            "archive_sha256": digest, "archive_bytes": bundle.stat().st_size,
            "validation": "passed", "git_commit": run_commit,
            "available_logs": task_logs,
        })
    if len(entries) != TASK_COUNT or len(seen_jobs) != TASK_COUNT:
        raise ValueError("campaign does not have 120 unique validated runs")
    expected_bundles = {
        member.removeprefix(f"{campaign_name}/")
        for _, member in files_to_archive
        if member.startswith(f"{campaign_name}/runs/")
    }
    runs_root = campaign_dir / "runs"
    actual_bundles = {
        path.relative_to(campaign_dir).as_posix()
        for path in runs_root.rglob("*") if path.is_file() or path.is_symlink()
    }
    if actual_bundles != expected_bundles:
        raise ValueError("campaign runs directory has missing or unexpected bundle files")

    finalizer_log_snapshots = []
    campaign_logs = campaign_dir / "logs"
    if campaign_logs.is_dir():
        for source in sorted(campaign_logs.iterdir()):
            if source.is_file() and not source.is_symlink():
                member = f"{campaign_name}/logs/{source.name}"
                if any(existing == member for _, existing in files_to_archive):
                    raise ValueError(f"duplicate campaign log name: {source.name}")
                files_to_archive.append((source, member))
                finalizer_log_snapshots.append(source.name)

    summary = {
        "schema": campaign_schema(strategy), "campaign": er4_campaign_name(strategy), "array_job_id": array_job_id,
        "checked_utc": datetime.now(timezone.utc).isoformat(),
        "verification_source": "athena-finalizer", "valid": True, "errors": [],
        "expected_runs": TASK_COUNT, "valid_runs": len(entries),
        "benchmark_count": len(BENCHMARKS), "repeat_count": len(REPEATS),
        "total_nested_archive_bytes": total_bytes,
        "git_commits_observed": sorted({entry["git_commit"] for entry in entries}),
        "available_logs": sorted(log_names), "missing_logs": sorted(missing_logs),
        "finalizer_log_snapshots": finalizer_log_snapshots,
        "runs": entries,
    }
    # The compressed outer tar contains 120 already-compressed tarballs. Leave
    # room for the aggregate beside the canonical hardlinked per-run bundles.
    free_bytes = shutil.disk_usage(campaign_dir).free
    reserve = max(128 * 1024 * 1024, total_bytes // 50)
    if free_bytes < total_bytes + reserve:
        raise OSError(f"not enough SCRATCH space for aggregate: free={free_bytes}, needed={total_bytes + reserve}")
    summary_path = campaign_dir / "campaign_summary.json"
    temporary_summary = campaign_dir / f".campaign_summary.{os.getpid()}.tmp"
    temporary_archive = campaign_dir / f".{archive.name}.{os.getpid()}.tmp"
    try:
        temporary_summary.write_text(json.dumps(summary, indent=2, ensure_ascii=False,
                                                allow_nan=False) + "\n", encoding="utf-8")
        os.replace(temporary_summary, summary_path)
        with tarfile.open(temporary_archive, "w:gz", compresslevel=1) as stream:
            stream.add(summary_path, arcname=f"{campaign_name}/campaign_summary.json")
            for source, member in files_to_archive:
                stream.add(source, arcname=member, recursive=False)
        if archive.exists() or checksum.exists():
            raise FileExistsError("campaign archive/checksum appeared during finalization")
        os.replace(temporary_archive, archive)
        checksum.write_text(f"{sha256(archive)}  {archive.name}\n", encoding="ascii")
    finally:
        temporary_summary.unlink(missing_ok=True)
        temporary_archive.unlink(missing_ok=True)
    return {"archive": str(archive), "checksum": str(checksum), "summary": str(summary_path),
            "valid_runs": len(entries)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    plan = subparsers.add_parser("plan")
    plan.add_argument("--campaign-dir", type=Path, required=True)
    plan.add_argument("--array-job-id", required=True)
    plan.add_argument("--git-commit", required=True)
    record = subparsers.add_parser("record")
    record.add_argument("--campaign-dir", type=Path, required=True)
    record.add_argument("--array-job-id", required=True)
    record.add_argument("--task-id", type=int, required=True)
    record.add_argument("--job-id", required=True)
    record.add_argument("--run-dir", type=Path, required=True)
    record.add_argument("--archive", type=Path, required=True)
    final = subparsers.add_parser("finalize")
    final.add_argument("--campaign-dir", type=Path, required=True)
    final.add_argument("--array-job-id", required=True)
    final.add_argument("--results-root", type=Path, required=True)
    final.add_argument("--logs-root", type=Path, required=True)
    final.add_argument("--sacct-file", type=Path, required=True)
    for action in (plan, record, final):
        action.add_argument("--strategy", choices=("best", "random"), default="best")
    args = parser.parse_args()
    marker = f"ATHENA_ER4_{args.strategy.upper()}"
    if args.command == "plan":
        if not args.array_job_id.isdecimal():
            raise ValueError("Array job ID must be decimal")
        document = plan_document(args.array_job_id, args.git_commit, args.strategy)
        write_json_exclusive(args.campaign_dir / "campaign_plan.json", document)
        print(f"{marker}_PLAN_OK={args.campaign_dir / 'campaign_plan.json'}")
    elif args.command == "record":
        result = record_task(args.campaign_dir, args.array_job_id, args.task_id,
                             args.job_id, args.run_dir, args.archive, args.strategy)
        print(f"{marker}_TASK_OK={result['task_id']}")
    else:
        result = finalize_campaign(args.campaign_dir, args.array_job_id,
                                   args.results_root, args.logs_root, args.sacct_file,
                                   args.strategy)
        print(f"{marker}_VALID_RUNS={result['valid_runs']}")
        print(f"{marker}_SUMMARY={result['summary']}")
        print(f"{marker}_ARCHIVE={result['archive']}")
        print(f"{marker}_SHA256={result['checksum']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
