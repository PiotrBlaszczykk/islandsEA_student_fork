import json
import sys
from datetime import datetime
import os
os.environ["RAY_DEDUP_LOGS"] = "0"
os.environ.setdefault("MPLBACKEND", "Agg")
os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")
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
from islands_desync.islands.topologies.ER1Topology import ER1Topology
from islands_desync.islands.topologies.ER2Topology import ER2Topology
from islands_desync.islands.topologies.ER3Topology import ER3Topology
from islands_desync.islands.topologies.ER4Topology import ER4Topology
from islands_desync.islands.topologies.WSTopology import WSTopology
from islands_desync.islands.topologies.WS1Topology import WS1Topology
from islands_desync.islands.topologies.WS2Topology import WS2Topology
from islands_desync.islands.topologies.WS3Topology import WS3Topology
from islands_desync.islands.topologies.WS4Topology import WS4Topology
from islands_desync.islands.topologies.JsonTopology import JsonTopology



def ray_init_kwargs(temp_dir):
    kwargs = {"_temp_dir": temp_dir}
    ray_num_cpus = os.environ.get("ISLANDS_RAY_NUM_CPUS")
    if ray_num_cpus:
        parsed_num_cpus = int(ray_num_cpus)
        if parsed_num_cpus <= 0:
            raise ValueError("ISLANDS_RAY_NUM_CPUS must be positive")
        kwargs["num_cpus"] = parsed_num_cpus
    return kwargs


def main():
    if sys.argv[2] != " ":
        #ray.init()
        ray.init(**ray_init_kwargs(sys.argv[2]))

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

    if topol=="torus":
        computation_refs = IslandRunner(TorusTopology, RandomSelect, params).create()
    if topol=="ring":
        computation_refs = IslandRunner(RingTopology, RandomSelect, params).create()
    if topol=="complete":
        computation_refs = IslandRunner(CompleteTopology, RandomSelect, params).create()
    if topol=="er":
        computation_refs = IslandRunner(ERTopology, RandomSelect, params).create()
    if topol=="er1":
        computation_refs = IslandRunner(ER1Topology, RandomSelect, params).create()
    if topol=="er2":
        computation_refs = IslandRunner(ER2Topology, RandomSelect, params).create()
    if topol=="er3":
        computation_refs = IslandRunner(ER3Topology, RandomSelect, params).create()
    if topol=="er4":
        computation_refs = IslandRunner(ER4Topology, RandomSelect, params).create()

    if topol=="ws":
        computation_refs = IslandRunner(WSTopology, RandomSelect, params).create()
    if topol=="ws1":
        computation_refs = IslandRunner(WS1Topology, RandomSelect, params).create()
    if topol=="ws2":
        computation_refs = IslandRunner(WS2Topology, RandomSelect, params).create()
    if topol=="ws3":
        computation_refs = IslandRunner(WS3Topology, RandomSelect, params).create()
    if topol=="ws4":
        computation_refs = IslandRunner(WS4Topology, RandomSelect, params).create()
    if topol.startswith("rt_"):
        computation_refs = IslandRunner(
            lambda size, create_object_method: JsonTopology(
                size, create_object_method, topol
            ),
            RandomSelect,
            params,
        ).create()


    #print("--- testpoint 1 ---")
    results = ray.get(computation_refs)
    #print(results, "--- testpoint 2 ---")           todo: w results moze da sie przeniec bestResult tej wyspy
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
