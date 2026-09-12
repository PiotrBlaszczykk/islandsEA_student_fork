from __future__ import annotations

import argparse
import csv
import io
import json
import statistics
import subprocess
import sys
from pathlib import Path


SACCT_FIELDS = (
    "JobIDRaw",
    "JobName",
    "State",
    "ExitCode",
    "ElapsedRaw",
    "AllocCPUS",
    "CPUTimeRAW",
    "Partition",
    "Account",
    "NodeList",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Policz przydzielone CPU-hours z zakonczonych jobow SLURM."
    )
    parser.add_argument("job_ids", nargs="+", help="Job ID jednego lub kilku pilotow")
    parser.add_argument("--planned-runs", type=int, default=1800)
    parser.add_argument("--overhead-percent", type=float, default=20.0)
    parser.add_argument("--json-output", type=Path)
    return parser.parse_args()


def load_job(job_id: str) -> dict[str, object]:
    command = [
        "sacct",
        "-j",
        job_id,
        "-nX",
        "-P",
        f"--format={','.join(SACCT_FIELDS)}",
    ]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    rows = list(csv.reader(io.StringIO(result.stdout), delimiter="|"))

    for values in rows:
        if values and values[-1] == "":
            values = values[:-1]
        if len(values) != len(SACCT_FIELDS):
            continue
        row = dict(zip(SACCT_FIELDS, values))
        if row["JobIDRaw"] == job_id:
            elapsed_seconds = int(row["ElapsedRaw"] or 0)
            allocated_cpus = int(row["AllocCPUS"] or 0)
            allocated_cpu_hours = allocated_cpus * elapsed_seconds / 3600.0
            cpu_time_raw = int(row["CPUTimeRAW"] or 0)
            return {
                **row,
                "elapsed_seconds": elapsed_seconds,
                "allocated_cpus": allocated_cpus,
                "allocated_cpu_hours": allocated_cpu_hours,
                "slurm_cpu_time_hours": cpu_time_raw / 3600.0,
            }

    raise RuntimeError(f"Brak glownego rekordu sacct dla joba {job_id}")


def main() -> int:
    args = parse_args()
    if args.planned_runs <= 0:
        raise ValueError("--planned-runs musi byc dodatnie")
    if args.overhead_percent < 0:
        raise ValueError("--overhead-percent nie moze byc ujemne")

    jobs = []
    for job_id in args.job_ids:
        try:
            jobs.append(load_job(job_id))
        except (OSError, subprocess.CalledProcessError, RuntimeError, ValueError) as exc:
            print(f"ERROR {job_id}: {exc}", file=sys.stderr)

    if not jobs:
        return 2

    print(
        "JobID | State | Elapsed[s] | AllocCPUS | Allocated CPUh | "
        "Partition | Account"
    )
    for job in jobs:
        print(
            f"{job['JobIDRaw']} | {job['State']} | {job['elapsed_seconds']} | "
            f"{job['allocated_cpus']} | {job['allocated_cpu_hours']:.4f} | "
            f"{job['Partition']} | {job['Account']}"
        )

    completed = [job for job in jobs if str(job["State"]).startswith("COMPLETED")]
    if not completed:
        print("Brak zakonczonych sukcesem pilotow; nie wykonuje projekcji.", file=sys.stderr)
        return 3

    cpu_hours = [float(job["allocated_cpu_hours"]) for job in completed]
    elapsed = [int(job["elapsed_seconds"]) for job in completed]
    mean_cpu_hours = statistics.mean(cpu_hours)
    median_cpu_hours = statistics.median(cpu_hours)
    projected_base = mean_cpu_hours * args.planned_runs
    projected_with_overhead = projected_base * (1.0 + args.overhead_percent / 100.0)

    summary = {
        "successful_pilot_count": len(completed),
        "planned_runs": args.planned_runs,
        "overhead_percent": args.overhead_percent,
        "mean_elapsed_seconds": statistics.mean(elapsed),
        "median_elapsed_seconds": statistics.median(elapsed),
        "mean_allocated_cpu_hours_per_run": mean_cpu_hours,
        "median_allocated_cpu_hours_per_run": median_cpu_hours,
        "projected_cpu_hours_base": projected_base,
        "projected_cpu_hours_with_overhead": projected_with_overhead,
        "jobs": jobs,
    }

    print("\nProjection")
    print(f"successful pilots: {summary['successful_pilot_count']}")
    print(f"mean elapsed: {summary['mean_elapsed_seconds']:.1f} s")
    print(f"mean allocated CPUh/run: {mean_cpu_hours:.4f}")
    print(f"planned runs: {args.planned_runs}")
    print(f"base total: {projected_base:.1f} CPUh")
    print(
        f"with {args.overhead_percent:.1f}% overhead: "
        f"{projected_with_overhead:.1f} CPUh"
    )

    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(f"JSON_READY={args.json_output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

