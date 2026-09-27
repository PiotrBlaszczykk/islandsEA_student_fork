#!/usr/bin/env python3
"""Index the ER4/best Athena array without changing portable per-run bundles."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
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


def plan_document(array_job_id: str, git_commit: str) -> dict:
    check_contract()
    graph = load_graph("er4")
    return {
        "schema": SCHEMA,
        "campaign": "er4_best",
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
                "selection": "best",
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


def validate_plan(plan: dict, array_job_id: str) -> None:
    expected = plan_document(array_job_id, plan.get("git_commit_at_submission", ""))
    for key in ("schema", "campaign", "array_job_id", "configuration", "benchmark_count", "repeat_count", "task_count", "tasks"):
        if plan.get(key) != expected[key]:
            raise ValueError(f"Campaign plan field {key} differs from the approved 120-task contract")


def record_task(campaign_dir: Path, array_job_id: str, task_id: int, job_id: str,
                run_dir: Path, archive: Path) -> dict:
    if not array_job_id.isdecimal() or not job_id.isdecimal():
        raise ValueError("SLURM job IDs must be decimal")
    if campaign_dir.name != f"er4_best_{array_job_id}":
        raise ValueError("Campaign directory is not tied to this array ID")
    plan = read_json(campaign_dir / "campaign_plan.json")
    validate_plan(plan, array_job_id)
    task = plan["tasks"][task_id - 1]
    if task["task_id"] != task_id:
        raise ValueError("Campaign task index mismatch")
    if run_dir.name != job_id or archive.name != f"run_{job_id}.tar.gz":
        raise ValueError("Run directory/archive does not match the actual SLURM job ID")
    validation = read_json(run_dir / "validation.json")
    for key, value in {
        "status": "passed", "valid": True, "mode": "full",
        "benchmark": task["benchmark"], "dimension": DIMENSION,
        "topology": "er4", "migrant_selection": "best",
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
    archive_sha256 = checksum.read_text(encoding="ascii").split()[0]
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
        "schema": SCHEMA,
        "status": "completed",
        "array_job_id": array_job_id,
        "task_id": task_id,
        "job_id": job_id,
        "benchmark": task["benchmark"],
        "dimension": DIMENSION,
        "repeat": task["repeat"],
        "topology": "er4",
        "migrant_selection": "best",
        "migrant_acceptance": "plain",
        "archive": (relative / archive.name).as_posix(),
        "archive_sha256": archive_sha256,
        "bundle_complete": True,
        "validation": "passed",
        "git_commit": run_commit,
    }
    write_json_exclusive(campaign_dir / "tasks" / f"task-{task_id:03d}.json", record)
    return record


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
    args = parser.parse_args()
    if args.command == "plan":
        if not args.array_job_id.isdecimal():
            raise ValueError("Array job ID must be decimal")
        document = plan_document(args.array_job_id, args.git_commit)
        write_json_exclusive(args.campaign_dir / "campaign_plan.json", document)
        print(f"ATHENA_ER4_BEST_PLAN_OK={args.campaign_dir / 'campaign_plan.json'}")
    else:
        result = record_task(args.campaign_dir, args.array_job_id, args.task_id,
                             args.job_id, args.run_dir, args.archive)
        print(f"ATHENA_ER4_BEST_TASK_OK={result['task_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
