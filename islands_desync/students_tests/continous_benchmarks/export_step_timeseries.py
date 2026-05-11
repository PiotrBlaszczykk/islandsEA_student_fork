#!/usr/bin/env python3
import argparse
import csv
import glob
import gzip
import json
import re
from pathlib import Path


RESULT_FILE_RE = re.compile(r"resultsEveryStepW(\d+)\.json$")


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return {}


def int_param(params, key, default=0):
    try:
        return int(params.get(key, default))
    except (TypeError, ValueError):
        return default


def metadata_from_params(run_dir):
    params = read_json(Path(run_dir) / "param.json")
    return {
        "run_dir": str(Path(run_dir)),
        "problem": params.get("problem", ""),
        "number_of_variables": params.get("number of variables", ""),
        "number_of_eval": params.get("number of eval", ""),
        "population_size": params.get("population size", ""),
        "offspring_population_size": params.get("offspring population size", ""),
        "number_of_islands": params.get("number of islands", ""),
        "migrant_selection_strategy": params.get("migrant_selection_type", ""),
        "migration_interval": params.get("migration interval", ""),
        "number_of_emigrants": params.get("number of emigrants", ""),
    }


def load_curves(run_dir):
    curves = []
    for file_path in sorted(glob.glob(str(Path(run_dir) / "resultsEveryStepW*.json"))):
        match = RESULT_FILE_RE.search(Path(file_path).name)
        if not match:
            continue
        data = read_json(file_path)
        points = {}
        for raw_step, raw_value in data.items():
            try:
                points[int(raw_step)] = float(raw_value)
            except (TypeError, ValueError):
                continue
        if points:
            curves.append((int(match.group(1)), points))
    return curves


def build_rows(run_dir):
    meta = metadata_from_params(run_dir)
    population_size = int_param(meta, "population_size")
    offspring_population_size = int_param(meta, "offspring_population_size", 1)
    max_evaluations = int_param(meta, "number_of_eval")
    curves = load_curves(run_dir)

    values_by_evaluation = {}
    raw_rows = []
    for island, points in curves:
        island_best_so_far = None
        for step in sorted(points):
            evaluation = population_size + step * offspring_population_size
            if max_evaluations:
                evaluation = min(evaluation, max_evaluations)
            best_fitness = points[step]
            island_best_so_far = (
                best_fitness
                if island_best_so_far is None
                else min(island_best_so_far, best_fitness)
            )
            values_by_evaluation.setdefault(evaluation, []).append(best_fitness)
            raw_rows.append(
                {
                    **meta,
                    "island": island,
                    "step": step,
                    "evaluation": evaluation,
                    "best_fitness": best_fitness,
                    "island_best_so_far": island_best_so_far,
                }
            )

    global_best_at_evaluation = {
        evaluation: min(values) for evaluation, values in values_by_evaluation.items()
    }
    global_best_so_far_by_evaluation = {}
    global_best_so_far = None
    for evaluation in sorted(global_best_at_evaluation):
        value = global_best_at_evaluation[evaluation]
        global_best_so_far = value if global_best_so_far is None else min(global_best_so_far, value)
        global_best_so_far_by_evaluation[evaluation] = global_best_so_far

    rows = []
    for row in raw_rows:
        evaluation = row["evaluation"]
        rows.append(
            {
                **row,
                "global_best_at_evaluation": global_best_at_evaluation.get(evaluation, ""),
                "global_best_so_far": global_best_so_far_by_evaluation.get(evaluation, ""),
            }
        )
    return rows


def write_csv(rows, output_csv):
    output_path = Path(output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)

    opener = gzip.open if output_path.suffix == ".gz" else open
    with opener(output_path, "wt", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved step timeseries CSV: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Export per-island, per-step benchmark fitness curves as long CSV."
    )
    parser.add_argument("run_dir", help="Run directory containing resultsEveryStepW*.json")
    parser.add_argument("output_csv", help="Output CSV path")
    args = parser.parse_args()

    rows = build_rows(args.run_dir)
    if not rows:
        raise SystemExit(f"No step data found in {args.run_dir}")
    write_csv(rows, args.output_csv)


if __name__ == "__main__":
    main()
