#!/usr/bin/env python3
import argparse
import csv
import glob
import json
import math
import re
import statistics
from pathlib import Path


def parse_result_file(path):
    result_path = Path(path)
    values = {}
    meta = {}
    number_re = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
    island_re = re.compile(rf"^\s*(\d+)\s+({number_re})\s*$")

    for raw_line in result_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        match = island_re.match(line)
        if match:
            values[int(match.group(1))] = float(match.group(2))
            continue

        if "MIGRANT SELECTION STRATEGY" in line:
            parts = line.replace("-", " ").split()
            if parts:
                meta["migrant_selection_strategy"] = parts[0]
        elif "MIGRANT ACCEPTATION STRATEGY" in line:
            marker = "MIGRANT ACCEPTATION STRATEGY"
            meta["migrant_acceptation_strategy"] = line.split(marker, 1)[1].replace("-", " ").strip()
        elif "TOPOLOGY" in line:
            parts = line.replace("-", " ").split()
            if parts:
                meta["topology"] = parts[0]
        elif line.startswith("Average result"):
            meta["average_result_reported"] = last_float(line)
        elif line.startswith("Best result"):
            meta["best_result_reported"] = last_float(line)
        elif line.startswith("Winner island"):
            winner = re.search(r"Winner island:\s*(\d+)", line)
            if winner:
                meta["winner_island"] = int(winner.group(1))
            reached = re.search(r"reached on\s*:\s*(\d+)/(\d+)", line)
            if reached:
                meta["winner_reached_count"] = int(reached.group(1))
                meta["winner_reached_denominator"] = int(reached.group(2))

    return values, meta


def last_float(text):
    matches = re.findall(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?", text)
    return float(matches[-1]) if matches else None


def read_param_json(run_dir):
    param_path = Path(run_dir) / "param.json"
    if not param_path.exists():
        return {}
    try:
        return json.loads(param_path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return {}


def robust_outliers(values):
    if not values:
        return []

    if len(values) >= 4:
        q1, _, q3 = statistics.quantiles(values, n=4, method="inclusive")
        iqr = q3 - q1
        threshold = q3 + 1.5 * iqr
    else:
        median = statistics.median(values)
        deviations = [abs(value - median) for value in values]
        mad = statistics.median(deviations)
        threshold = median + 3 * mad if mad else median

    return [value for value in values if value > threshold]


def summarize_curves(run_dir, thresholds):
    files = sorted(glob.glob(str(Path(run_dir) / "resultsEveryStepW*.json")))
    if not files:
        return {}

    curves = []
    for file_path in files:
        try:
            data = json.loads(Path(file_path).read_text(encoding="utf-8", errors="replace"))
        except json.JSONDecodeError:
            continue
        points = {int(k): float(v) for k, v in data.items()}
        if points:
            curves.append(points)

    if not curves:
        return {}

    steps = sorted(set().union(*(curve.keys() for curve in curves)))
    global_best = []
    for step in steps:
        candidates = [curve[step] for curve in curves if step in curve]
        if candidates:
            global_best.append((step, min(candidates)))

    summary = {
        "curve_file_count": len(curves),
        "first_step": steps[0],
        "last_step": steps[-1],
        "global_best_start": global_best[0][1],
        "global_best_end": global_best[-1][1],
        "global_best_improvement": global_best[0][1] - global_best[-1][1],
    }

    for threshold in thresholds:
        key = f"first_step_global_best_le_{threshold:g}"
        summary[key] = ""
        for step, value in global_best:
            if value <= threshold:
                summary[key] = step
                break

    return summary


def summarize_run(run_dir, thresholds):
    run_path = Path(run_dir)
    values_by_island, result_meta = parse_result_file(run_path / "___RESULT.txt")
    param = read_param_json(run_path)

    values = [value for _, value in sorted(values_by_island.items())]
    outliers = robust_outliers(values)

    row = {
        "run_dir": str(run_path),
        "problem": param.get("problem", ""),
        "number_of_variables": param.get("number of variables", ""),
        "number_of_eval": param.get("number of eval", ""),
        "population_size": param.get("population size", ""),
        "offspring_population_size": param.get("offspring population size", ""),
        "number_of_islands": param.get("number of islands", result_meta.get("winner_reached_denominator", "")),
        "topology": result_meta.get("topology", ""),
        "migrant_selection_strategy": param.get(
            "migrant_selection_type", result_meta.get("migrant_selection_strategy", "")
        ),
        "migrant_acceptation_strategy": result_meta.get("migrant_acceptation_strategy", ""),
        "migration_interval": param.get("migration interval", ""),
        "number_of_emigrants": param.get("number of emigrants", ""),
        "island_result_count": len(values),
        "best_final": min(values) if values else "",
        "mean_final": statistics.mean(values) if values else "",
        "median_final": statistics.median(values) if values else "",
        "worst_final": max(values) if values else "",
        "std_final": statistics.pstdev(values) if len(values) > 1 else 0,
        "mean_minus_median": (statistics.mean(values) - statistics.median(values)) if values else "",
        "outlier_count_robust": len(outliers),
        "outlier_values_robust": ";".join(f"{value:.12g}" for value in outliers),
        "winner_island": result_meta.get("winner_island", ""),
        "winner_reached_count": result_meta.get("winner_reached_count", ""),
        "reported_average_result": result_meta.get("average_result_reported", ""),
        "reported_best_result": result_meta.get("best_result_reported", ""),
    }

    row.update(summarize_curves(run_path, thresholds))
    return row


def discover_run_dirs(paths, recursive):
    result = []
    for raw_path in paths:
        path = Path(raw_path)
        if path.is_file() and path.name == "___RESULT.txt":
            result.append(path.parent)
        elif path.is_dir() and (path / "___RESULT.txt").exists():
            result.append(path)
        elif recursive and path.is_dir():
            for result_file in path.rglob("___RESULT.txt"):
                result.append(result_file.parent)
    return sorted(set(result))


def write_outputs(rows, output_prefix):
    output_path = Path(output_prefix)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    json_path = output_path.with_suffix(".json")
    csv_path = output_path.with_suffix(".csv")

    json_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")

    fieldnames = []
    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    print(f"Saved summary CSV: {csv_path}")
    print(f"Saved summary JSON: {json_path}")


def main():
    parser = argparse.ArgumentParser(description="Summarize island benchmark result directories.")
    parser.add_argument("paths", nargs="+", help="Run dirs or roots containing run dirs")
    parser.add_argument("--recursive", action="store_true", help="Search recursively for ___RESULT.txt")
    parser.add_argument("--output-prefix", default="experiment_summary", help="Output path without extension")
    parser.add_argument(
        "--thresholds",
        default="1,0.1,0.01",
        help="Comma-separated thresholds for global-best curve summaries",
    )
    args = parser.parse_args()

    thresholds = [float(item) for item in args.thresholds.split(",") if item.strip()]
    run_dirs = discover_run_dirs(args.paths, args.recursive)
    if not run_dirs:
        raise SystemExit("No run directories with ___RESULT.txt found.")

    rows = [summarize_run(run_dir, thresholds) for run_dir in run_dirs]
    write_outputs(rows, args.output_prefix)

    print(f"Summarized runs: {len(rows)}")


if __name__ == "__main__":
    main()
