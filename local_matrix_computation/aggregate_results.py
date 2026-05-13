#!/usr/bin/env python3
import argparse
import csv
import json
import re
import statistics
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent
DEFAULT_RESULTS_ROOT = ROOT / "results"
DEFAULT_RUNS_ROOT = ROOT / "runs"
DEFAULT_OUTPUT_DIR = ROOT / "analysis"

NUMERIC_COLUMNS = {
    "number_of_variables",
    "number_of_eval",
    "population_size",
    "offspring_population_size",
    "number_of_islands",
    "migration_interval",
    "number_of_emigrants",
    "island_result_count",
    "best_final",
    "mean_final",
    "median_final",
    "worst_final",
    "std_final",
    "mean_minus_median",
    "outlier_count_robust",
    "winner_island",
    "winner_reached_count",
    "reported_average_result",
    "reported_best_result",
    "curve_file_count",
    "first_step",
    "last_step",
    "global_best_start",
    "global_best_end",
    "global_best_improvement",
    "convergence_start_best",
    "convergence_end_best",
    "convergence_improvement",
    "convergence_eval_min",
    "convergence_eval_max",
    "auc_global_best_so_far",
    "mean_global_best_so_far",
    "best_at_25pct_budget",
    "best_at_50pct_budget",
    "best_at_75pct_budget",
    "best_at_100pct_budget",
    "eval_to_25pct_improvement",
    "eval_to_50pct_improvement",
    "eval_to_75pct_improvement",
    "eval_to_90pct_improvement",
    "eval_to_final_best",
}

TOPOLOGY_METRIC_COLUMNS = [
    "edge_count_directed",
    "self_loops",
    "density_directed_no_self",
    "min_out_degree",
    "max_out_degree",
    "avg_out_degree",
    "min_in_degree",
    "max_in_degree",
    "avg_in_degree",
    "weak_component_count",
]

GROUP_KEYS = [
    "experiment_key",
    "experiment_name",
    "problem_kind",
    "problem",
    "number_of_variables",
    "number_of_eval",
    "number_of_islands",
    "topology",
    "migrant_selection_strategy",
    "migrant_acceptation_strategy",
    "migration_interval",
    "number_of_emigrants",
]

SUMMARY_METRICS = [
    "best_final",
    "mean_final",
    "median_final",
    "worst_final",
    "std_final",
    "global_best_end",
    "global_best_improvement",
    "last_step",
    "convergence_improvement",
    "auc_global_best_so_far",
    "mean_global_best_so_far",
    "best_at_25pct_budget",
    "best_at_50pct_budget",
    "best_at_75pct_budget",
    "best_at_100pct_budget",
    "eval_to_25pct_improvement",
    "eval_to_50pct_improvement",
    "eval_to_75pct_improvement",
    "eval_to_90pct_improvement",
    "eval_to_final_best",
]


def safe_read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8", errors="replace"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def read_csv_one(path):
    with Path(path).open(newline="", encoding="utf-8", errors="replace") as handle:
        rows = list(csv.DictReader(handle))
    return rows[0] if rows else {}


def read_csv_rows(path):
    try:
        with Path(path).open(newline="", encoding="utf-8", errors="replace") as handle:
            return list(csv.DictReader(handle))
    except FileNotFoundError:
        return []


def to_number(value):
    if value in ("", None):
        return ""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return value
    if number.is_integer():
        return int(number)
    return number


def to_float(value):
    if value in ("", None):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def load_job_index(runs_root):
    all_jobs = safe_read_json(Path(runs_root) / "all_jobs.json").get("jobs", [])
    by_name_and_date = {}
    for job in all_jobs:
        name = job.get("benchmark_name")
        if not name:
            continue
        by_name_and_date[(name, job.get("date_tag", ""))] = job
    return by_name_and_date


def infer_experiment_key(summary_path, results_root):
    try:
        relative = Path(summary_path).resolve().relative_to(Path(results_root).resolve())
    except ValueError:
        return ""
    return relative.parts[0] if relative.parts else ""


def infer_experiment_name(summary_path, results_root):
    try:
        relative = Path(summary_path).resolve().relative_to(Path(results_root).resolve())
    except ValueError:
        return ""
    return relative.parts[1] if len(relative.parts) > 1 else ""


def parse_benchmark_name(name, summary_row):
    result = {}
    if not name:
        return result

    parts = name.split("_")
    if len(parts) >= 2 and parts[0] in ("local", "smoke"):
        result["problem_kind"] = parts[1]

    repeat_match = re.search(r"_r(\d+)$", name)
    if repeat_match:
        result["repeat"] = int(repeat_match.group(1))

    strategy = summary_row.get("migrant_selection_strategy", "")
    topology = summary_row.get("topology", "")
    islands = summary_row.get("number_of_islands", "")
    problem = summary_row.get("problem", "")

    result.update(
        {
            "problem": problem,
            "topology": topology,
            "islands": islands,
            "migrant_strategy": strategy,
        }
    )
    return result


def latest_value_at_or_before(points, target_evaluation):
    if not points:
        return ""

    candidate = points[0][1]
    for evaluation, value in points:
        if evaluation > target_evaluation:
            break
        candidate = value
    return candidate


def trapezoid_auc(points):
    if len(points) < 2:
        return 0 if points else ""

    auc = 0
    for (left_eval, left_value), (right_eval, right_value) in zip(points, points[1:]):
        auc += (right_eval - left_eval) * ((left_value + right_value) / 2)
    return auc


def convergence_metrics(export_dir, summary):
    rows = read_csv_rows(Path(export_dir) / "fitness_timeseries.csv")
    if not rows:
        return {}

    by_evaluation = {}
    for row in rows:
        evaluation = to_float(row.get("evaluation"))
        value = to_float(row.get("global_best_so_far"))
        if evaluation is None or value is None:
            continue
        current = by_evaluation.get(evaluation)
        by_evaluation[evaluation] = value if current is None else min(current, value)

    points = sorted(by_evaluation.items())
    if not points:
        return {}

    start_best = points[0][1]
    end_best = points[-1][1]
    improvement = start_best - end_best
    eval_min = points[0][0]
    eval_max = points[-1][0]
    configured_budget = to_float(summary.get("number_of_eval")) or eval_max
    auc = trapezoid_auc(points)
    mean_value = auc / (eval_max - eval_min) if len(points) > 1 and eval_max > eval_min else start_best

    metrics = {
        "convergence_start_best": start_best,
        "convergence_end_best": end_best,
        "convergence_improvement": improvement,
        "convergence_eval_min": eval_min,
        "convergence_eval_max": eval_max,
        "auc_global_best_so_far": auc,
        "mean_global_best_so_far": mean_value,
        "best_at_25pct_budget": latest_value_at_or_before(points, configured_budget * 0.25),
        "best_at_50pct_budget": latest_value_at_or_before(points, configured_budget * 0.50),
        "best_at_75pct_budget": latest_value_at_or_before(points, configured_budget * 0.75),
        "best_at_100pct_budget": latest_value_at_or_before(points, configured_budget),
        "eval_to_final_best": "",
    }

    for fraction in (0.25, 0.50, 0.75, 0.90):
        key = f"eval_to_{int(fraction * 100)}pct_improvement"
        metrics[key] = ""
        if improvement > 0:
            threshold = start_best - improvement * fraction
            for evaluation, value in points:
                if value <= threshold:
                    metrics[key] = evaluation
                    break

    for evaluation, value in points:
        if value <= end_best:
            metrics["eval_to_final_best"] = evaluation
            break

    return metrics


def collect_rows(results_root, runs_root):
    job_by_name_and_date = load_job_index(runs_root)
    rows = []

    for summary_path in sorted(Path(results_root).rglob("summary.csv")):
        export_dir = summary_path.parent
        summary = read_csv_one(summary_path)
        manifest = safe_read_json(export_dir / "export_manifest.json")
        topology_metrics = safe_read_json(export_dir / "topology_metrics.json")

        benchmark_name = manifest.get("benchmark_name", export_dir.name)
        experiment_key = infer_experiment_key(summary_path, results_root)
        experiment_name = infer_experiment_name(summary_path, results_root)
        job = job_by_name_and_date.get((benchmark_name, experiment_name), {})
        parsed = parse_benchmark_name(benchmark_name, summary)

        row = {
            "result_dir": str(export_dir),
            "summary_csv": str(summary_path),
            "benchmark_name": benchmark_name,
            "experiment_key": job.get("experiment_key", experiment_key),
            "experiment_name": job.get("date_tag", experiment_name),
            "problem_kind": job.get("problem_kind", parsed.get("problem_kind", "")),
            "job_index": job.get("job_index", ""),
            "repeat": job.get("repeat", parsed.get("repeat", "")),
        }

        for key, value in summary.items():
            row[key] = to_number(value) if key in NUMERIC_COLUMNS else value

        for key, value in convergence_metrics(export_dir, summary).items():
            row[key] = value

        if not row.get("problem_kind"):
            row["problem_kind"] = parsed.get("problem_kind", "")

        for key in TOPOLOGY_METRIC_COLUMNS:
            row[f"topology_{key}"] = topology_metrics.get(key, "")

        row["topology_weak_component_sizes"] = ";".join(
            str(item) for item in topology_metrics.get("weak_component_sizes", [])
        )
        rows.append(row)

    return rows


def mean(values):
    values = [value for value in values if value is not None]
    return statistics.mean(values) if values else ""


def pstdev(values):
    values = [value for value in values if value is not None]
    return statistics.pstdev(values) if len(values) > 1 else 0 if values else ""


def summarize_group(rows):
    result = {key: rows[0].get(key, "") for key in GROUP_KEYS}
    result["run_count"] = len(rows)
    result["repeat_values"] = ";".join(str(row.get("repeat", "")) for row in rows)
    result["complete_three_repeats"] = len(rows) >= 3

    for metric in SUMMARY_METRICS:
        values = [to_float(row.get(metric)) for row in rows]
        present = [value for value in values if value is not None]
        result[f"{metric}_mean"] = mean(values)
        result[f"{metric}_std"] = pstdev(values)
        result[f"{metric}_min"] = min(present) if present else ""
        result[f"{metric}_max"] = max(present) if present else ""

    return result


def comparison_groups(rows):
    groups = defaultdict(list)
    for row in rows:
        key = tuple(row.get(item, "") for item in GROUP_KEYS)
        groups[key].append(row)
    return [summarize_group(group_rows) for group_rows in groups.values()]


def rank_rows(rows, rank_keys, ranked_field, rank_column, metric="best_final_mean"):
    grouped = defaultdict(list)
    for row in rows:
        key = tuple(row.get(item, "") for item in rank_keys)
        grouped[key].append(row)

    ranked = []
    for group_rows in grouped.values():
        ordered = sorted(
            group_rows,
            key=lambda row: (
                to_float(row.get(metric)) is None,
                to_float(row.get(metric)) or float("inf"),
                row.get(ranked_field, ""),
            ),
        )
        for rank, row in enumerate(ordered, start=1):
            ranked.append(
                {
                    **row,
                    rank_column: rank,
                    "ranked_factor": row.get(ranked_field, ""),
                    "ranked_metric": metric,
                }
            )
    return ranked


def write_csv(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(
        description="Aggregate local matrix exported summaries into comparison-ready CSV files."
    )
    parser.add_argument(
        "--results-root",
        default=str(DEFAULT_RESULTS_ROOT),
        help="Root containing local_matrix_computation/results exports.",
    )
    parser.add_argument(
        "--runs-root",
        default=str(DEFAULT_RUNS_ROOT),
        help="Root containing generated run manifests/all_jobs.json.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory where aggregate CSV/JSON files will be written.",
    )
    args = parser.parse_args()

    rows = collect_rows(args.results_root, args.runs_root)
    if not rows:
        raise SystemExit(f"No summary.csv files found under {args.results_root}")

    grouped = comparison_groups(rows)
    strategy_ranked = rank_rows(
        grouped,
        [
            "experiment_key",
            "experiment_name",
            "problem_kind",
            "problem",
            "number_of_variables",
            "number_of_eval",
            "number_of_islands",
            "topology",
            "migrant_acceptation_strategy",
            "migration_interval",
            "number_of_emigrants",
        ],
        "migrant_selection_strategy",
        "strategy_rank_by_best_final_mean",
    )
    strategy_convergence_ranked = rank_rows(
        grouped,
        [
            "experiment_key",
            "experiment_name",
            "problem_kind",
            "problem",
            "number_of_variables",
            "number_of_eval",
            "number_of_islands",
            "topology",
            "migrant_acceptation_strategy",
            "migration_interval",
            "number_of_emigrants",
        ],
        "migrant_selection_strategy",
        "strategy_rank_by_eval_to_90pct_improvement_mean",
        metric="eval_to_90pct_improvement_mean",
    )
    topology_ranked = rank_rows(
        grouped,
        [
            "experiment_key",
            "experiment_name",
            "problem_kind",
            "problem",
            "number_of_variables",
            "number_of_eval",
            "number_of_islands",
            "migrant_selection_strategy",
            "migrant_acceptation_strategy",
            "migration_interval",
            "number_of_emigrants",
        ],
        "topology",
        "topology_rank_by_best_final_mean",
    )
    topology_convergence_ranked = rank_rows(
        grouped,
        [
            "experiment_key",
            "experiment_name",
            "problem_kind",
            "problem",
            "number_of_variables",
            "number_of_eval",
            "number_of_islands",
            "migrant_selection_strategy",
            "migrant_acceptation_strategy",
            "migration_interval",
            "number_of_emigrants",
        ],
        "topology",
        "topology_rank_by_eval_to_90pct_improvement_mean",
        metric="eval_to_90pct_improvement_mean",
    )

    output_dir = Path(args.output_dir)
    write_csv(output_dir / "combined_runs.csv", rows)
    write_json(output_dir / "combined_runs.json", rows)
    write_csv(output_dir / "comparison_groups.csv", grouped)
    write_json(output_dir / "comparison_groups.json", grouped)
    write_csv(output_dir / "strategy_ranking.csv", strategy_ranked)
    write_csv(output_dir / "strategy_convergence_ranking.csv", strategy_convergence_ranked)
    write_csv(output_dir / "topology_ranking.csv", topology_ranked)
    write_csv(output_dir / "topology_convergence_ranking.csv", topology_convergence_ranked)

    print(f"Runs aggregated: {len(rows)}")
    print(f"Comparison groups: {len(grouped)}")
    print(f"Output directory: {output_dir.resolve()}")


if __name__ == "__main__":
    main()
