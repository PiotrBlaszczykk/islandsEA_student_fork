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

    print("parametry wej do start.py: 1 -",sys.argv[1],"2 -",sys.argv[2],"3 -",sys.argv[3],"4 -",sys.argv[4],"5 -",sys.argv[5],"6 -",sys.argv[6],"7 -",sys.argv[7],sys.argv[8],sys.argv[9], "---" ,len(sys.argv), "---",  sys.argv[0]) 

    if sys.argv[2] != " ":
        ray.init()

    #topol = "ring"
    #topol = "torus"
    #topol = "complete"
    #topol = "er"
    topol=sys.argv[6] #7
    strateg=sys.argv[7] #8


    params = RunAlgorithmParams(
        island_count=int(sys.argv[1]),
        number_of_emigrants=int(sys.argv[2]), #3
        migration_interval=int(sys.argv[3]), #4
        dda=sys.argv[4], #5
        tta=sys.argv[5], #6
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

    print("w Start_cyf - przed ray.get")

    results = ray.get(computation_refs)

    print("w Start_cyf - po ray.get")

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
