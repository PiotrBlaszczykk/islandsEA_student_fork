#!/usr/bin/env python3
"""Package already validated Complete/best runs after the null-parameters bug."""

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import campaign_tools as campaign

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hpc_benchmarks"))
import run_bundle


def require(condition, message):
    if not condition:
        raise ValueError(message)


def inspect_task(root, plan, task_id, array_job_id):
    task = campaign.task_for(plan, task_id)
    task_dir = root / "tasks" / f"task-{task_id:03d}"
    record = campaign.read_json(task_dir / "task.json")
    validation = campaign.read_json(task_dir / "validation.json")
    pointer_path = task_dir / "result_pointer.json"
    pointer = campaign.read_json(pointer_path)
    job_id = str(record.get("job_id", ""))
    execution_array_id = str(record.get("execution_array_job_id", array_job_id))

    require(all(record.get(key) == task[key] for key in ("task_id", "benchmark", "repeat")),
            f"task {task_id}: record/plan mismatch")
    require(str(record.get("array_job_id")) == array_job_id
            and execution_array_id == array_job_id,
            f"task {task_id}: original array identity mismatch")
    require(record.get("status") == "failed" and record.get("exit_code") == 74,
            f"task {task_id}: expected original packaging failure (74)")
    require(job_id.isdecimal(), f"task {task_id}: invalid original job ID")
    require(validation.get("valid") is True and not validation.get("errors")
            and validation.get("task_id") == task_id
            and str(validation.get("job_id")) == job_id
            and str(validation.get("array_job_id")) == array_job_id
            and str(validation.get("execution_array_job_id", array_job_id)) == array_job_id,
            f"task {task_id}: scientific validation missing or failed")

    raw_value = pointer.get("run_directory")
    require(isinstance(raw_value, str) and raw_value, f"task {task_id}: missing raw run pointer")
    raw = Path(raw_value).resolve()
    require(raw.is_relative_to(root / "storage" / "results" / "runs"),
            f"task {task_id}: raw run is outside this campaign")
    metadata = campaign.read_json(raw / "run_metadata.json")
    require(pointer.get("run_id") == metadata.get("run_id"),
            f"task {task_id}: pointer/run identity mismatch")
    require(metadata.get("provenance", {}).get("git_commit") == plan["git_commit_at_submission"],
            f"task {task_id}: original Git provenance mismatch")
    metadata_errors = campaign.validate_metadata(metadata, task, array_job_id, job_id)
    require(not metadata_errors, f"task {task_id}: " + "; ".join(metadata_errors))

    output = root / "runs"
    require(not any((output / f"run_{job_id}{suffix}").exists()
                    for suffix in ("", ".tar.gz", ".tar.gz.sha256")),
            f"task {task_id}: existing export requires separate review")
    require(not (output / f".run_{job_id}.lock").exists(),
            f"task {task_id}: export lock exists")
    return task_dir, record, pointer_path, job_id


def load_campaign(root):
    root = Path(root).resolve()
    require(campaign.CAMPAIGN == "complete_best" and root.name == "complete_best",
            "recovery applies only to complete_best")
    require(not (root / "complete_best.tar.gz").exists(), "campaign archive already exists")
    plan = campaign.load_plan(root / "campaign_plan.json")
    submission = campaign.read_json(root / "submission.json")
    array_job_id = str(submission.get("array_job_id", ""))
    require(array_job_id.isdecimal(), "missing original array job ID")
    return root, plan, array_job_id


def preflight(root):
    root, plan, array_job_id = load_campaign(root)
    for task_id in range(1, 121):
        inspect_task(root, plan, task_id, array_job_id)
    print(f"COMPLETE_BEST_RECOVERY_PREFLIGHT_OK validated=120 original_array={array_job_id}")


def recover_task(root, task_id, recovery_job_id):
    root, plan, array_job_id = load_campaign(root)
    require(str(recovery_job_id).isdecimal(), "missing recovery SLURM job ID")
    task_dir, record, pointer, job_id = inspect_task(root, plan, task_id, array_job_id)
    result = run_bundle.export_run(
        output_root=root / "runs", platform="ares", job_id=job_id,
        pointer=pointer, job_dir=task_dir, log_dir=root / "logs", exit_code=74,
    )
    verification = run_bundle.verify_archive(result["archive"])
    require(verification.get("verified") is True and verification.get("complete") is True
            and verification.get("validation") == "passed" and verification.get("job_id") == job_id,
            f"task {task_id}: recovered bundle did not verify")
    verification_path = task_dir / "bundle_verification.json"
    campaign.write_json(verification_path, verification)
    campaign.write_json(task_dir / "task.json", {
        **record,
        "status": "completed",
        "exit_code": 0,
        "original_job_exit_code": 74,
        "original_finished_utc": record.get("finished_utc"),
        "recovery_job_id": str(recovery_job_id),
        "recovered_utc": campaign.utc_now(),
        "archive": str(Path(result["archive"]).resolve()),
        "verification": str(verification_path.resolve()),
    })
    print(f"COMPLETE_BEST_RECOVERY_TASK_OK={task_id} original_job={job_id} recovery_job={recovery_job_id}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preflight", "task"))
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--task-id", type=int)
    parser.add_argument("--recovery-job-id")
    args = parser.parse_args()
    if args.action == "preflight":
        preflight(args.campaign_dir)
    else:
        require(args.task_id is not None and args.recovery_job_id,
                "task requires --task-id and --recovery-job-id")
        recover_task(args.campaign_dir, args.task_id, args.recovery_job_id)


if __name__ == "__main__":
    main()
