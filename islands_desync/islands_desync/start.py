import json
import sys
from datetime import datetime
import os
os.environ["RAY_DEDUP_LOGS"] = "0"
from islands_desync.geneticAlgorithm.utils.matplotlib_setup import (
    configure_headless_matplotlib,
)

configure_headless_matplotlib()

import ray
from islands_desync.islands.core.IslandRunner import IslandRunner
from islands_desync.islands.selectAlgorithm import RandomSelect

from islands_desync.geneticAlgorithm.run_hpc.run_algorithm_params import (
    RunAlgorithmParams,
)
from islands_desync.geneticAlgorithm.utils.filename import get_run_output_root
import importlib
from islands_desync.islands.topologies.study import TOPOLOGIES, validate_study



def main():
    if len(sys.argv) != 10:
        raise ValueError("Expected 9 positional arguments; prefer hpc_benchmarks/run_benchmark.py")
    count, name = int(sys.argv[1]), sys.argv[7]
    validate_study(count, name)
    topology_class_name = TOPOLOGIES[name]
    topology_class = getattr(importlib.import_module(
        "islands_desync.islands.topologies." + topology_class_name), topology_class_name)
    topology = topology_class(count, lambda i: i)
    topology.create(12, 12) if name == "torus" else topology.create()
    ray_runtime_env = {
        "env_vars": {
            "MPLBACKEND": os.environ["MPLBACKEND"],
            "MPLCONFIGDIR": os.environ["MPLCONFIGDIR"],
            **{
                key: value
                for key, value in os.environ.items()
                if key.startswith("ISLANDS_")
            },
        }
    }

    if sys.argv[2] != " ":
        #ray.init()
        ray.init(_temp_dir=sys.argv[2], runtime_env=ray_runtime_env)

    #topol = "ring"
    #topol = "torus"
    #topol = "complete"
    #topol = "er"
    topol=sys.argv[7]
    strateg=sys.argv[8]
    strateg2=sys.argv[9]


    params = RunAlgorithmParams(
        island_count=int(sys.argv[1]),
        number_of_emigrants=int(sys.argv[3]),
        migration_interval=int(sys.argv[4]),
        dda=sys.argv[5],
        tta=sys.argv[6],
        series_number=1,
        topology=topol,
        strategy=strateg,
        strategy2=strateg2
    )

    computation_refs = IslandRunner(topology_class, RandomSelect, params).create()

    #print("--- testpoint 1 ---")
    results = ray.get(computation_refs)
    #print(results, "--- testpoint 2 ---")           todo: w results moze da sie przeniec bestResult tej wyspy
    iterations = {result["island"]: result for result in results}

    summary_directory = get_run_output_root()
    summary_directory.mkdir(parents=True, exist_ok=True)
    with (summary_directory / (
        "iterations_per_second"
        + datetime.now().strftime("%m-%d-%Y_%H%M")
        + ".json"
    )).open("w", encoding="utf-8") as f:
        json.dump(iterations, f)


if __name__ == "__main__":
    main()
