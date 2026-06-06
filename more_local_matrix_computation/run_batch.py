#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent
DEFAULT_RUNNER = (
    REPO_ROOT
    / "islands_desync"
    / "students_tests"
    / "continous_benchmarks"
    / "run_local_benchmark.py"
)


def load_batch(path):
    batch_path = Path(path)
    if not batch_path.is_absolute():
        batch_path = REPO_ROOT / batch_path
    with batch_path.open(encoding="utf-8") as handle:
        batch = json.load(handle)
    return batch_path, batch


def merged_job(defaults, job):
    merged = dict(defaults)
    merged.update(job)
    return merged


def export_dir_for(job):
    return (
        REPO_ROOT
        / job["output_base"]
        / job["date_tag"]
        / f"{job['time_tag']}_{job['benchmark_name']}"
    )


def build_command(job, python_executable, runner, overwrite_existing=False):
    command = [
        python_executable,
        str(runner),
        "--benchmark-name",
        job["benchmark_name"],
        "--problem",
        job["problem"],
        "--variables",
        str(job["variables"]),
        "--evaluations",
        str(job["evaluations"]),
        "--population-size",
        str(job["population_size"]),
        "--offspring-population-size",
        str(job["offspring_population_size"]),
        "--islands",
        str(job["islands"]),
        "--topology",
        job["topology"],
        "--migrant-strategy",
        job["migrant_strategy"],
        "--accept-strategy",
        job["accept_strategy"],
        "--migrants",
        str(job["migrants"]),
        "--migration-interval",
        str(job["migration_interval"]),
        "--date-tag",
        job["date_tag"],
        "--time-tag",
        job["time_tag"],
        "--output-base",
        str(REPO_ROOT / job["output_base"]),
    ]
    if job.get("ray_num_cpus") is not None:
        command.extend(["--ray-num-cpus", str(job["ray_num_cpus"])])
    if overwrite_existing:
        command.append("--overwrite-existing")
    if job.get("compress_timeseries"):
        command.append("--compress-timeseries")
    if job.get("cleanup_run_dir"):
        command.append("--cleanup-run-dir")
    if job.get("random_topology_dir"):
        command.extend(
            [
                "--random-topology-dir",
                str(REPO_ROOT / job["random_topology_dir"]),
            ]
        )
    return command


def main():
    parser = argparse.ArgumentParser(
        description="Run one more_local_matrix_computation batch JSON sequentially."
    )
    parser.add_argument("batch_json", help="Path to a more_local_matrix_computation/runs/*.json file")
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python executable to use for each local benchmark.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Run only the first N jobs from the selected batch.",
    )
    parser.add_argument(
        "--only",
        help="Run only jobs whose benchmark_name contains this text.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Run even when summary.csv already exists in the export directory.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands without executing them.",
    )
    args = parser.parse_args()

    batch_path, batch = load_batch(args.batch_json)
    defaults = batch.get("defaults", {})
    runner = batch.get("execution", {}).get("runner")
    runner_path = REPO_ROOT / runner if runner else DEFAULT_RUNNER

    jobs = [merged_job(defaults, job) for job in batch["jobs"]]
    if args.only:
        jobs = [job for job in jobs if args.only in job["benchmark_name"]]
    if args.limit is not None:
        jobs = jobs[: args.limit]

    print(f"Batch: {batch_path}")
    print(f"Jobs selected: {len(jobs)}")
    print(f"Runner: {runner_path}")

    for position, job in enumerate(jobs, start=1):
        export_dir = export_dir_for(job)
        summary_path = export_dir / "summary.csv"
        if summary_path.exists() and not args.force:
            print(f"[{position}/{len(jobs)}] SKIP {job['benchmark_name']} (summary exists)")
            continue

        command = build_command(
            job,
            args.python,
            runner_path,
            overwrite_existing=args.force,
        )
        print(f"[{position}/{len(jobs)}] RUN {job['benchmark_name']}")
        print("+", " ".join(command))
        if args.dry_run:
            continue

        completed = subprocess.run(command, cwd=REPO_ROOT)
        if completed.returncode != 0:
            raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
