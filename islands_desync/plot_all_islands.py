#!/usr/bin/env python3
import glob
import json
import os
import sys
from pathlib import Path

import matplotlib.pyplot as plt


def read_run_params(run_dir):
    param_path = Path(run_dir) / "param.json"
    if not param_path.exists():
        return {}
    try:
        return json.loads(param_path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return {}


def int_param(params, key, default=0):
    try:
        return int(params.get(key, default))
    except (TypeError, ValueError):
        return default


def main() -> int:
    if len(sys.argv) not in (2, 3):
        print("Usage: plot_all_islands.py <run_dir> [output_png]")
        return 2

    run_dir = sys.argv[1]
    output_png = (
        sys.argv[2]
        if len(sys.argv) == 3
        else os.path.join(run_dir, "fitness_all_islands.png")
    )

    files = sorted(glob.glob(os.path.join(run_dir, "resultsEveryStepW*.json")))
    if not files:
        print(f"No resultsEveryStepW*.json files found in: {run_dir}")
        return 1

    params = read_run_params(run_dir)
    population_size = int_param(params, "population size")
    offspring_population_size = int_param(params, "offspring population size", 1)
    max_evaluations = int_param(params, "number of eval")

    all_y_values = []

    plt.figure(figsize=(10, 6))
    for file_path in files:
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)

        steps = sorted(int(k) for k in data.keys())
        xs = steps
        if population_size and offspring_population_size:
            xs = [population_size + step * offspring_population_size for step in steps]
            if max_evaluations:
                xs = [min(x, max_evaluations) for x in xs]
        ys = [data[str(step)] for step in steps]
        all_y_values.extend(ys)
        name = (
            os.path.basename(file_path)
            .replace("resultsEveryStep", "")
            .replace(".json", "")
        )
        plt.plot(xs, ys, linewidth=1, label=name)

    if any(y <= 0 for y in all_y_values):
        plt.yscale("symlog", linthresh=1e-3)
    else:
        plt.yscale("log")
    plt.xlabel("evaluation")
    plt.ylabel("best fitness")
    plt.title("Best fitness per evaluation (all islands)")
    plt.legend(fontsize=7, ncol=2)
    plt.tight_layout()

    os.makedirs(os.path.dirname(output_png), exist_ok=True)
    plt.savefig(output_png, dpi=150)
    print(f"Saved: {output_png}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
