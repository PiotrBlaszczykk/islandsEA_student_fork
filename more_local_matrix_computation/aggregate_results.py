#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent
LOCAL_AGGREGATOR = REPO_ROOT / "local_matrix_computation" / "aggregate_results.py"


def main():
    args = sys.argv[1:]
    if not any(arg == "--results-root" or arg.startswith("--results-root=") for arg in args):
        args.extend(["--results-root", str(ROOT / "results")])
    if not any(arg == "--runs-root" or arg.startswith("--runs-root=") for arg in args):
        args.extend(["--runs-root", str(ROOT / "runs")])
    if not any(arg == "--output-dir" or arg.startswith("--output-dir=") for arg in args):
        args.extend(["--output-dir", str(ROOT / "analysis")])

    command = [sys.executable, str(LOCAL_AGGREGATOR), *args]
    completed = subprocess.run(command, cwd=REPO_ROOT)
    raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
