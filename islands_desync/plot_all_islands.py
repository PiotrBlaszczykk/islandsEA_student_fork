#!/usr/bin/env python3
import glob
import json
import os
import sys

import matplotlib.pyplot as plt


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

    all_y_values = []

    plt.figure(figsize=(10, 6))
    for file_path in files:
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)

        xs = sorted(int(k) for k in data.keys())
        ys = [data[str(x)] for x in xs]
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
    plt.xlabel("step")
    plt.ylabel("best fitness")
    plt.title("Best fitness per step (all islands)")
    plt.legend(fontsize=7, ncol=2)
    plt.tight_layout()

    os.makedirs(os.path.dirname(output_png), exist_ok=True)
    plt.savefig(output_png, dpi=150)
    print(f"Saved: {output_png}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
