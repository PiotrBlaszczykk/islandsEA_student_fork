#!/usr/bin/env python3
import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent
RUN_BATCH = ROOT / "run_batch.py"
DEFAULT_GROUPS = ["continous_fixed_toplogies", "descrete_fixed_toplogies"]


def batch_index(path):
    try:
        return int(path.name.split("_", 2)[1])
    except (IndexError, ValueError):
        return 0


def resolve_groups(values):
    groups = values or DEFAULT_GROUPS
    resolved = []
    for value in groups:
        candidate = Path(value)
        if candidate.is_absolute():
            group_dir = candidate
        else:
            group_dir = ROOT / "runs" / value
            if not group_dir.is_dir():
                group_dir = REPO_ROOT / value
        if not group_dir.is_dir():
            raise SystemExit(f"Group directory not found: {value}")
        resolved.append(group_dir)
    return resolved


def collect_batches(group_dirs, pattern):
    batches = []
    for group_dir in group_dirs:
        group_batches = sorted(group_dir.glob(pattern), key=lambda path: (batch_index(path), path.name))
        batches.extend(group_batches)
    return batches


def build_command(args, batch_path):
    command = [args.python, str(RUN_BATCH), str(batch_path)]
    if args.job_python:
        command.extend(["--python", args.job_python])
    if args.force:
        command.append("--force")
    if args.dry_run:
        command.append("--dry-run")
    if args.only:
        command.extend(["--only", args.only])
    if args.limit_jobs is not None:
        command.extend(["--limit", str(args.limit_jobs)])
    return command


def append_line(path, text):
    with path.open("a", encoding="utf-8", errors="replace") as handle:
        handle.write(text)
        if not text.endswith("\n"):
            handle.write("\n")


def run_with_tee(command, cwd, log_path):
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8", errors="replace") as log_handle:
        log_handle.write("+ " + " ".join(command) + "\n")
        log_handle.flush()
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        assert process.stdout is not None
        for line in process.stdout:
            print(line, end="")
            log_handle.write(line)
        return process.wait()


def main():
    parser = argparse.ArgumentParser(
        description="Run the full more_local_matrix_computation matrix sequentially."
    )
    parser.add_argument(
        "--groups",
        nargs="+",
        help=(
            "Groups to run. Defaults to continous_fixed_toplogies and "
            "descrete_fixed_toplogies. Accepts group names or directories."
        ),
    )
    parser.add_argument("--pattern", default="batch_*.json")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--job-python", help="Python executable used by benchmark jobs.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing exports.")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without running Ray jobs.")
    parser.add_argument("--only", help="Run only jobs whose benchmark_name contains this text.")
    parser.add_argument("--limit-jobs", type=int, help="Pass --limit N to each batch.")
    parser.add_argument("--limit-batches", type=int, help="Run only the first N selected batches.")
    parser.add_argument(
        "--continue-on-failure",
        action="store_true",
        help="Continue with next batch when one batch exits non-zero.",
    )
    parser.add_argument(
        "--log-dir",
        help="Directory for logs. Default: more_local_matrix_computation/batch_logs/all.",
    )
    args = parser.parse_args()

    group_dirs = resolve_groups(args.groups)
    batches = collect_batches(group_dirs, args.pattern)
    if args.limit_batches is not None:
        batches = batches[: args.limit_batches]
    if not batches:
        raise SystemExit("No batch files selected.")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir = Path(args.log_dir) if args.log_dir else ROOT / "batch_logs" / "all"
    if not log_dir.is_absolute():
        log_dir = REPO_ROOT / log_dir
    log_dir.mkdir(parents=True, exist_ok=True)
    master_log = log_dir / f"run_all_{timestamp}.log"

    header = [
        "More local matrix run_all",
        f"Groups: {', '.join(str(path) for path in group_dirs)}",
        f"Selected batches: {len(batches)}",
        f"Dry run: {args.dry_run}",
        f"Log dir: {log_dir}",
        "",
    ]
    for line in header:
        print(line)
        append_line(master_log, line)

    failed = []
    started_at = datetime.now()
    for position, batch_path in enumerate(batches, start=1):
        command = build_command(args, batch_path)
        label = f"[{position}/{len(batches)}] {batch_path.parent.name}/{batch_path.name}"
        batch_log = log_dir / f"{batch_path.parent.name}_{batch_path.stem}_{timestamp}.log"

        print(f"{label} RUN")
        append_line(master_log, f"{label} RUN")
        append_line(master_log, f"LOG {batch_log}")
        append_line(master_log, "+ " + " ".join(command))

        batch_started = datetime.now()
        return_code = run_with_tee(command, REPO_ROOT, batch_log)
        elapsed = datetime.now() - batch_started
        status = f"{label} EXIT {return_code} elapsed={elapsed}"
        print(status)
        append_line(master_log, status)

        if return_code != 0:
            failed.append((batch_path, return_code))
            if not args.continue_on_failure:
                break

    total_elapsed = datetime.now() - started_at
    summary = f"Done. selected_batches={len(batches)} failed={len(failed)} elapsed={total_elapsed}"
    print(summary)
    append_line(master_log, summary)

    if failed:
        print("Failed batches:")
        append_line(master_log, "Failed batches:")
        for path, return_code in failed:
            line = f"- {path}: exit {return_code}"
            print(line)
            append_line(master_log, line)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
