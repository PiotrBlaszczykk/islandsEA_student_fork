#!/usr/bin/env python3
import argparse
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent
RUN_BATCH = ROOT / "run_batch.py"


def resolve_batch_dir(value):
    candidate = Path(value)
    candidates = []
    if candidate.is_absolute():
        candidates.append(candidate)
    else:
        candidates.extend(
            [
                REPO_ROOT / candidate,
                ROOT / "runs" / candidate,
            ]
        )

    for path in candidates:
        if path.is_dir():
            return path

    raise SystemExit(f"Batch directory not found: {value}")


def batch_index(path):
    match = re.match(r"batch_(\d+)_", path.name)
    if match:
        return int(match.group(1))
    return None


def parse_range(value):
    if not value:
        return None, None

    match = re.fullmatch(r"(\d+)(?:-(\d+))?", value.strip())
    if not match:
        raise SystemExit("Use --range in form N or N-M, for example --range 2-5")

    start = int(match.group(1))
    end = int(match.group(2) or match.group(1))
    if end < start:
        raise SystemExit("--range end must be >= start")
    return start, end


def select_batches(batch_dir, pattern, start, end, limit_batches):
    batches = sorted(
        batch_dir.glob(pattern),
        key=lambda path: (batch_index(path) is None, batch_index(path) or 0, path.name),
    )

    selected = []
    for path in batches:
        index = batch_index(path)
        if start is not None and (index is None or index < start):
            continue
        if end is not None and (index is None or index > end):
            continue
        selected.append(path)

    if limit_batches is not None:
        selected = selected[:limit_batches]

    return selected


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
        description="Run a selected range of more_local_matrix_computation batch JSON files sequentially."
    )
    parser.add_argument(
        "batch_dir",
        help=(
            "Directory with batch_*.json files. Accepts full path, repo-relative "
            "path, or group name such as continous_fixed_toplogies."
        ),
    )
    parser.add_argument(
        "--range",
        dest="batch_range",
        help="Inclusive batch index range, for example 1-3 or 7.",
    )
    parser.add_argument("--start", type=int, help="First batch index to run.")
    parser.add_argument("--end", type=int, help="Last batch index to run.")
    parser.add_argument(
        "--limit-batches",
        type=int,
        help="Run only the first N selected batch files.",
    )
    parser.add_argument(
        "--pattern",
        default="batch_*.json",
        help="Glob pattern inside batch_dir. Default: batch_*.json",
    )
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python executable used to run run_batch.py.",
    )
    parser.add_argument(
        "--job-python",
        help="Python executable passed through to run_batch.py for benchmark jobs.",
    )
    parser.add_argument(
        "--limit-jobs",
        type=int,
        help="Pass --limit N to each batch.",
    )
    parser.add_argument("--only", help="Pass --only TEXT to each batch.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Pass --force to each batch. Use only when rerunning/overwriting.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print and log commands without executing benchmark jobs.",
    )
    parser.add_argument(
        "--continue-on-failure",
        action="store_true",
        help="Continue with the next batch when one batch exits non-zero.",
    )
    parser.add_argument(
        "--log-dir",
        help="Directory for per-batch logs. Default: more_local_matrix_computation/batch_logs/<group>.",
    )
    args = parser.parse_args()

    range_start, range_end = parse_range(args.batch_range)
    start = args.start if args.start is not None else range_start
    end = args.end if args.end is not None else range_end
    if start is not None and end is not None and end < start:
        raise SystemExit("--end must be >= --start")

    batch_dir = resolve_batch_dir(args.batch_dir)
    selected = select_batches(
        batch_dir,
        args.pattern,
        start=start,
        end=end,
        limit_batches=args.limit_batches,
    )
    if not selected:
        raise SystemExit(f"No batches selected in {batch_dir}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir = Path(args.log_dir) if args.log_dir else ROOT / "batch_logs" / batch_dir.name
    if not log_dir.is_absolute():
        log_dir = REPO_ROOT / log_dir
    log_dir.mkdir(parents=True, exist_ok=True)
    master_log = log_dir / f"range_{timestamp}.log"

    header = [
        f"Batch dir: {batch_dir}",
        f"Selected batches: {len(selected)}",
        f"Log dir: {log_dir}",
        f"Dry run: {args.dry_run}",
        "",
    ]
    for line in header:
        print(line)
        append_line(master_log, line)

    failed = []
    started_at = datetime.now()
    for position, batch_path in enumerate(selected, start=1):
        index = batch_index(batch_path)
        label = f"[{position}/{len(selected)}] batch_{index:03d}" if index else f"[{position}/{len(selected)}]"
        batch_log = log_dir / f"{batch_path.stem}_{timestamp}.log"
        command = build_command(args, batch_path)

        message = f"{label} RUN {batch_path.name}"
        print(message)
        append_line(master_log, message)
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
    summary = f"Done. selected={len(selected)} failed={len(failed)} elapsed={total_elapsed}"
    print(summary)
    append_line(master_log, summary)

    if failed:
        print("Failed batches:")
        append_line(master_log, "Failed batches:")
        for path, return_code in failed:
            line = f"- {path.name}: exit {return_code}"
            print(line)
            append_line(master_log, line)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
