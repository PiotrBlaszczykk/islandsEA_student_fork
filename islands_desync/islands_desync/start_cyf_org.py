import json
import sys
from datetime import datetime
import os
os.environ["RAY_DEDUP_LOGS"] = "0"
import ray
from islands.core.IslandRunner import IslandRunner
from islands.selectAlgorithm import RandomSelect
from islands.topologies import RingTopology

from islands_desync.geneticAlgorithm.run_hpc.run_algorithm_params import (
    RunAlgorithmParams,
)
from islands_desync.islands.topologies.TorusTopology import TorusTopology
from islands_desync.islands.topologies.CompleteTopology import CompleteTopology
from islands_desync.islands.topologies.ERTopology import ERTopology

def main():
    if sys.argv[2] != " ":
        ray.init()

    #topol = "ring"
    #topol = "torus"
    #topol = "complete"
    #topol = "er"
    topol=sys.argv[7]
    strateg=sys.argv[8]


    params = RunAlgorithmParams(
        island_count=int(sys.argv[1]),
        number_of_emigrants=int(sys.argv[3]),
        migration_interval=int(sys.argv[4]),
        dda=sys.argv[5],
        tta=sys.argv[6],
        series_number=1,
        topology=topol,
        strategy=strateg,
    )

    if topol=="torus":
        computation_refs = IslandRunner(TorusTopology, RandomSelect, params).create()
    if topol=="ring":
        computation_refs = IslandRunner(RingTopology, RandomSelect, params).create()
    if topol=="complete":
        computation_refs = IslandRunner(CompleteTopology, RandomSelect, params).create()
    if topol=="er":
        computation_refs = IslandRunner(ERTopology, RandomSelect, params).create()

    results = ray.get(computation_refs)

    iterations = {result["island"]: result for result in results}

    with open(
        "logs/"
        + "iterations_per_second"
        + datetime.now().strftime("%m-%d-%Y_%H%M")
        + ".json",
        "w",
    ) as f:
        json.dump(iterations, f)


if __name__ == "__main__":
    main()
