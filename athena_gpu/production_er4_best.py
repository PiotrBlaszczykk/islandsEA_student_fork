#!/usr/bin/env python3
"""Frozen task map for ER4/best and ER4/random Athena batches."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "islands_desync"))

from islands_desync.geneticAlgorithm.utils.benchmarks_refined import (
    BENCHMARKS,
    CONTINUOUS_BENCHMARKS,
    DISCRETE_BENCHMARKS,
    create_evaluator,
)
from islands_desync.islands.topologies.fixed_graph import load_graph


REPEATS = (1, 2, 3)
TASK_COUNT = 120
ER4_SHA256 = "469cc283543dcc60d5bf8f07db2eabfb12cab34637f4a6d26bca51d07f85cccc"
BENCHMARK_ORDER_SHA256 = "52bba92358d7462897dd81f5d64df0ab645339cf10dba6e6ba2fde404b925c16"


def check_contract() -> None:
    if len(CONTINUOUS_BENCHMARKS) != 30 or len(DISCRETE_BENCHMARKS) != 10:
        raise ValueError("The approved 30+10 benchmark suite changed")
    if len(BENCHMARKS) * len(REPEATS) != TASK_COUNT or len(set(BENCHMARKS)) != 40:
        raise ValueError("The production array must contain exactly 120 unique configurations")
    ordered_names = ("\n".join(BENCHMARKS) + "\n").encode("utf-8")
    if hashlib.sha256(ordered_names).hexdigest() != BENCHMARK_ORDER_SHA256:
        raise ValueError("The benchmark order differs from the completed ER4/best comparison campaign")
    graph = load_graph("er4")
    if graph["nodes"] != 144 or graph["provenance"]["adjacency_sha256"] != ER4_SHA256:
        raise ValueError("The approved 144-node ER4 graph changed")


def configuration(task_id: int) -> tuple[str, int]:
    if not 1 <= task_id <= TASK_COUNT:
        raise ValueError(f"Array task ID must be in 1..{TASK_COUNT}")
    benchmark_index, repeat_index = divmod(task_id - 1, len(REPEATS))
    return BENCHMARKS[benchmark_index], REPEATS[repeat_index]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true")
    group.add_argument("--task-id", type=int)
    parser.add_argument("--strategy", choices=("best", "random"), default="best")
    args = parser.parse_args()
    check_contract()
    if args.check:
        # Fail before submitting the array if any selected 200D instance or
        # fixed CEC data file is unavailable in the current checkout.
        for benchmark in BENCHMARKS:
            create_evaluator(benchmark, 200)
        print(f"ATHENA_ER4_{args.strategy.upper()}_TASKS={TASK_COUNT}")
        print(f"ATHENA_ER4_SHA256={ER4_SHA256}")
        print(f"ATHENA_ER4_BENCHMARK_ORDER_SHA256={BENCHMARK_ORDER_SHA256}")
    else:
        print("\t".join(map(str, configuration(args.task_id))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
