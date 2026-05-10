#!/usr/bin/env python3
import json
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]
OUTPUT_DIR = SCRIPT_DIR / "smoke_outputs"


def run_command(args):
    print("+ " + " ".join(str(arg) for arg in args))
    subprocess.run(args, cwd=REPO_ROOT, check=True)


def ensure_synthetic_run():
    run_dir = OUTPUT_DIR / "synthetic_ring_run"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "param.json").write_text(
        json.dumps(
            {
                "problem": "Sphere",
                "number of variables": "30",
                "number of eval": "600",
                "population size": "16",
                "offspring population size": "4",
                "number of islands": "12",
                "migrant_selection_type": "random",
                "migration interval": "20",
                "number of emigrants": "2",
            }
        ),
        encoding="utf-8",
    )
    result_lines = [
        "0.10",
        "3",
        "",
        " -- -- -- random MIGRANT SELECTION STRATEGY -- -- --",
        " -- -- -- MIGRANT ACCEPTATION STRATEGY BEZ -- -- --",
        " -- -- -- ring TOPOLOGY -- -- --",
        "------------------------------------",
        "Average result:  0.35",
        "------------------------------------",
        "Best result   : 0.10",
        "Winner island: 3 (this result was reached on : 1/12 islands) (number of results taken to avg: 12)",
        "",
    ]
    result_lines.extend(f"{i} {0.1 + i * 0.03}" for i in range(12))
    (run_dir / "___RESULT.txt").write_text("\n".join(result_lines) + "\n", encoding="utf-8")
    return run_dir


def candidate_runs():
    candidates = [
        (
            "torus_144_report",
            "torus",
            144,
            REPO_ROOT / "raport" / "benchmarki" / "plot_exports" / "260407" / "220314_144tr_test",
        ),
        (
            "er2_150_report",
            "er2",
            150,
            REPO_ROOT / "raport" / "benchmarki" / "plot_exports" / "260505" / "235703_150er2_test",
        ),
    ]

    existing = [
        (name, topology, islands, path)
        for name, topology, islands, path in candidates
        if (path / "___RESULT.txt").exists()
    ]

    if existing:
        return existing

    synthetic = ensure_synthetic_run()
    return [("synthetic_ring", "ring", 12, synthetic)]


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    runs = candidate_runs()

    for name, topology, islands, run_dir in runs:
        run_command(
            [
                sys.executable,
                SCRIPT_DIR / "plot_topology.py",
                "--topology",
                topology,
                "--islands",
                str(islands),
                "--result",
                run_dir / "___RESULT.txt",
                "--output",
                OUTPUT_DIR / f"{name}_topology.png",
                "--metrics-output",
                OUTPUT_DIR / f"{name}_topology_metrics.json",
            ]
        )

    summarize_args = [
        sys.executable,
        SCRIPT_DIR / "summarize_experiments.py",
        "--output-prefix",
        OUTPUT_DIR / "smoke_summary",
    ] + [str(run_dir) for _, _, _, run_dir in runs]
    run_command(summarize_args)

    print("")
    print(f"Smoke outputs: {OUTPUT_DIR}")
    print("OK: topology plotting and result summarization completed.")


if __name__ == "__main__":
    main()

