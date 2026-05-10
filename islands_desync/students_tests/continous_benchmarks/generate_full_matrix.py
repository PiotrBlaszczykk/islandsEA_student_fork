#!/usr/bin/env python3
import csv
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT = SCRIPT_DIR / "benchmark_matrix_full_continuous.csv"

PROBLEMS = ["sphere", "rastrigin", "ackley"]
TOPOLOGIES = ["ring", "torus", "complete"]
MIGRANT_STRATEGIES = ["random", "best", "worst", "maxDistance"]
ISLAND_COUNTS = [48, 144, 288]
REPEATS = [1, 2, 3]

NUMBER_OF_VARIABLES = 200
NUMBER_OF_EVALUATIONS = 8000
POPULATION_SIZE = 16
OFFSPRING_POPULATION_SIZE = 4
NUMBER_OF_MIGRANTS = 5
MIGRATION_INTERVAL = 5
MIGRANT_ACCEPT_STRATEGY = "BEZ"


def resources_for(islands):
    if islands <= 48:
        return 4, 96, "01:00:00"
    if islands <= 96:
        return 6, 144, "01:30:00"
    if islands <= 144:
        return 8, 192, "02:00:00"
    return 16, 384, "04:00:00"


def main():
    fieldnames = [
        "benchmark_name",
        "problem",
        "number_of_variables",
        "number_of_evaluations",
        "population_size",
        "offspring_population_size",
        "number_of_islands",
        "topology",
        "migrant_strategy",
        "migrant_accept_strategy",
        "number_of_migrants",
        "migration_interval",
        "repeat",
        "nodes",
        "ntasks",
        "time_limit",
    ]

    rows = []
    for problem in PROBLEMS:
        for topology in TOPOLOGIES:
            for migrant_strategy in MIGRANT_STRATEGIES:
                for islands in ISLAND_COUNTS:
                    nodes, ntasks, time_limit = resources_for(islands)
                    for repeat in REPEATS:
                        rows.append(
                            {
                                "benchmark_name": (
                                    f"full_{problem}_{topology}_{islands}_"
                                    f"{migrant_strategy}_r{repeat}"
                                ),
                                "problem": problem,
                                "number_of_variables": NUMBER_OF_VARIABLES,
                                "number_of_evaluations": NUMBER_OF_EVALUATIONS,
                                "population_size": POPULATION_SIZE,
                                "offspring_population_size": OFFSPRING_POPULATION_SIZE,
                                "number_of_islands": islands,
                                "topology": topology,
                                "migrant_strategy": migrant_strategy,
                                "migrant_accept_strategy": MIGRANT_ACCEPT_STRATEGY,
                                "number_of_migrants": NUMBER_OF_MIGRANTS,
                                "migration_interval": MIGRATION_INTERVAL,
                                "repeat": repeat,
                                "nodes": nodes,
                                "ntasks": ntasks,
                                "time_limit": time_limit,
                            }
                        )

    with OUTPUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {OUTPUT}")


if __name__ == "__main__":
    main()
