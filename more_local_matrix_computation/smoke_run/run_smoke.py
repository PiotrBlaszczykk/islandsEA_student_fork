#!/usr/bin/env python3
import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parents[1]
RUN_BATCH = REPO_ROOT / "more_local_matrix_computation" / "run_batch.py"
SMOKE_BATCH = ROOT / "runs" / "mixed_fixed_toplogies" / "smoke_batch.json"


def main():
    parser = argparse.ArgumentParser(
        description="Run the tiny more_local_matrix_computation smoke batch."
    )
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python executable used to run more_local_matrix_computation/run_batch.py.",
    )
    parser.add_argument(
        "--job-python",
        help="Python executable passed through to the benchmark job runner.",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing smoke exports.")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without running Ray.")
    parser.add_argument("--limit", type=int, help="Run only the first N smoke jobs.")
    args = parser.parse_args()

    if not SMOKE_BATCH.exists():
        generator = ROOT / "generate_smoke_configs.py"
        completed = subprocess.run([args.python, str(generator)], cwd=REPO_ROOT)
        if completed.returncode != 0:
            raise SystemExit(completed.returncode)

    command = [args.python, str(RUN_BATCH), str(SMOKE_BATCH)]
    if args.job_python:
        command.extend(["--python", args.job_python])
    if args.force:
        command.append("--force")
    if args.dry_run:
        command.append("--dry-run")
    if args.limit is not None:
        command.extend(["--limit", str(args.limit)])

    print("+", " ".join(command))
    completed = subprocess.run(command, cwd=REPO_ROOT)
    raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
