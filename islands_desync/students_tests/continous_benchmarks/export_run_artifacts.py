#!/usr/bin/env python3
import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
ISLANDS_ROOT = SCRIPT_DIR.parents[1]
REPO_ROOT = ISLANDS_ROOT.parent


def safe_name(value):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value).strip()).strip("_")


def read_param(run_dir):
    param_path = Path(run_dir) / "param.json"
    if not param_path.exists():
        return {}
    try:
        return json.loads(param_path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return {}


def infer_date_time(run_dir):
    parts = Path(run_dir).parts
    if "logs" in parts:
        logs_idx = parts.index("logs")
        if len(parts) > logs_idx + 3:
            date_tag = parts[logs_idx + 1]
            run_name = parts[logs_idx + 3]
            time_tag = run_name.split(" ", 1)[0]
            if date_tag and time_tag:
                return date_tag, time_tag
    now = datetime.now()
    return now.strftime("%y%m%d"), now.strftime("%H%M%S")


def run_tool(args, required=False):
    print("+", " ".join(str(arg) for arg in args))
    completed = subprocess.run(args)
    if required and completed.returncode != 0:
        raise SystemExit(completed.returncode)
    return completed.returncode


def export_artifacts(
    run_dir,
    output_base,
    benchmark_name=None,
    topology=None,
    islands=None,
    compress_timeseries=False,
    random_topology_dir=None,
):
    run_path = Path(run_dir).resolve()
    if not run_path.exists():
        raise SystemExit(f"Run directory does not exist: {run_path}")

    param = read_param(run_path)
    if islands is None and param.get("number of islands"):
        islands = int(param["number of islands"])

    date_tag, time_tag = infer_date_time(run_path)
    export_name = safe_name(benchmark_name or run_path.name)
    output_base = Path(output_base)
    export_dir = output_base / date_tag / f"{time_tag}_{export_name}"
    export_dir.mkdir(parents=True, exist_ok=True)

    python = sys.executable

    run_tool(
        [
            python,
            str(ISLANDS_ROOT / "plot_all_islands.py"),
            str(run_path),
            str(export_dir / "fitness_all_islands.png"),
        ]
    )

    timeseries_path = export_dir / "fitness_timeseries.csv"
    if compress_timeseries:
        timeseries_path = timeseries_path.with_suffix(".csv.gz")
    run_tool(
        [
            python,
            str(SCRIPT_DIR / "export_step_timeseries.py"),
            str(run_path),
            str(timeseries_path),
        ]
    )

    for file_name in ("___RESULT.txt", "___WINNER.txt", "param.json"):
        source = run_path / file_name
        if source.exists():
            shutil.copy2(source, export_dir / file_name)

    if topology and islands:
        topology_command = [
            python,
            str(SCRIPT_DIR / "plot_topology.py"),
            "--topology",
            topology,
            "--islands",
            str(islands),
            "--result",
            str(run_path / "___RESULT.txt"),
            "--output",
            str(export_dir / "topology_with_fitness.png"),
            "--metrics-output",
            str(export_dir / "topology_metrics.json"),
        ]
        if random_topology_dir:
            topology_command.extend(["--random-topology-dir", str(random_topology_dir)])
        run_tool(topology_command)
    else:
        print("Skipping topology plot: pass --topology and --islands to enable it.")

    run_tool(
        [
            python,
            str(SCRIPT_DIR / "summarize_experiments.py"),
            str(run_path),
            "--output-prefix",
            str(export_dir / "summary"),
        ]
    )

    manifest = {
        "run_dir": str(run_path),
        "export_dir": str(export_dir.resolve()),
        "benchmark_name": benchmark_name or run_path.name,
        "topology": topology,
        "islands": islands,
        "compress_timeseries": compress_timeseries,
        "random_topology_dir": str(random_topology_dir) if random_topology_dir else None,
    }
    (export_dir / "export_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    print(f"EXPORT_DIR: {export_dir.resolve()}")
    return export_dir


def main():
    parser = argparse.ArgumentParser(description="Export benchmark run artifacts.")
    parser.add_argument("run_dir", help="Existing logs/... run directory")
    parser.add_argument("--benchmark-name", help="Name used in the export directory")
    parser.add_argument("--topology", help="Topology name for topology plot")
    parser.add_argument("--islands", type=int, help="Island count for topology plot")
    parser.add_argument(
        "--output-base",
        default=str(REPO_ROOT / "students_benchmarks_results" / "continous" / "fixed_topologies" / "local_runs"),
        help="Base directory for exported artifacts",
    )
    parser.add_argument(
        "--compress-timeseries",
        action="store_true",
        help="Write fitness_timeseries.csv.gz instead of plain CSV",
    )
    parser.add_argument("--random-topology-dir", help="Directory with rt_* JSON graph files")
    args = parser.parse_args()

    export_artifacts(
        args.run_dir,
        args.output_base,
        benchmark_name=args.benchmark_name,
        topology=args.topology,
        islands=args.islands,
        compress_timeseries=args.compress_timeseries,
        random_topology_dir=args.random_topology_dir,
    )


if __name__ == "__main__":
    main()
