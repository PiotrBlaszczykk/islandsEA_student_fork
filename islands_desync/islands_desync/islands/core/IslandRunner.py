import time
from typing import List

import ray

from islands_desync.geneticAlgorithm.run_hpc.run_algorithm_params import (
    RunAlgorithmParams,
)
from islands_desync.islands.core.Island import Island
from islands_desync.islands.core.SignalActor import SignalActor
from islands_desync.islands.topologies.TorusTopology import TorusTopology


class IslandRunner:
    def __init__(self, CreateTopology, SelectAlgorithm, params: RunAlgorithmParams):
        self.CreateTopology = CreateTopology
        self.SelectAlgorithm = SelectAlgorithm
        self.params: RunAlgorithmParams = params

    def create(self) -> List[ray.ObjectRef]:
        islands = [
            Island.remote(i, self.SelectAlgorithm())
            for i in range(self.params.island_count)
        ]

        topology = self.CreateTopology(
            self.params.island_count, lambda i: islands[i]
        )

        print("\n TOPOLOGIA \n\n",topology.__dict__,"\n\n")

        if isinstance(topology, TorusTopology):
            topology = topology.create(12, self.params.island_count // 12)
            #topology = topology.create(10, self.params.island_count // 10) #//5
        else:
            topology = topology.create()

        print("w IslandRunner.py przed signal actor")

        signal_actor = SignalActor.remote(self.params.island_count)

        print("przed computations")

        computations = [
            ray.get(
                islands[0].start.remote(islands[0], topology[0], self.params, signal_actor)
            )
        ]

        time.sleep(15)

        print("przed computations.extend")

        computations.extend(
            ray.get(
                [
                    island.start.remote(island, topology[island_id], self.params, signal_actor)
                    for island_id, island in enumerate(islands[1:], start=1)
                ]
            )
        )

        print("po computation.extend")

        aaa = [computation.start.remote() for computation in computations]
        print ("przed return") #,aaa)

        return aaa
