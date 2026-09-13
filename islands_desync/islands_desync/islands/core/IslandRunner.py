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

        # Build the topology once and retain both the actor handle and its
        # stable numeric id.  Generating it a second time would be unsafe for
        # randomized topologies and deriving ids through extra Ray calls would
        # add one RPC per migrated individual.
        topology = self.CreateTopology(
            self.params.island_count, lambda i: (i, islands[i])
        )

        print("\n TOPOLOGIA \n\n",topology.__dict__,"\n\n")

        if isinstance(topology, TorusTopology):
            if self.params.torus_rows is not None and self.params.torus_columns is not None:
                if (
                    self.params.torus_rows < 2
                    or self.params.torus_columns < 2
                    or self.params.torus_rows * self.params.torus_columns
                    != self.params.island_count
                ):
                    raise ValueError(
                        "Explicit torus rows and columns must both be >=2 and cover every island"
                    )
                topology_pairs = topology.create(
                    self.params.torus_columns,
                    self.params.torus_rows,
                )
            else:
                topology_pairs = topology.create(12, self.params.island_count // 12)
            #topology = topology.create(10, self.params.island_count // 10) #//5
        else:
            topology_pairs = topology.create()

        topology_handles = {
            island_id: [actor for _, actor in neighbours]
            for island_id, neighbours in topology_pairs.items()
        }
        topology_ids = {
            island_id: [destination_id for destination_id, _ in neighbours]
            for island_id, neighbours in topology_pairs.items()
        }

        print("w IslandRunner.py przed signal actor")

        signal_actor = SignalActor.remote(self.params.island_count)

        print("przed computations")

        computations = [
            ray.get(
                islands[0].start.remote(
                    islands[0],
                    topology_handles[0],
                    topology_ids[0],
                    self.params,
                    signal_actor,
                )
            )
        ]

        # Island 0 creates shared run metadata/directories in the historical
        # implementation.  A returned actor handle does not mean that its Ray
        # constructor has finished, so explicitly wait before creating the
        # other Computation actors.
        ray.get(
            computations[0].ready.remote(),
            timeout=self.params.actor_startup_timeout,
        )

        time.sleep(15)

        print("przed computations.extend")

        computations.extend(
            ray.get(
                [
                    island.start.remote(
                        island,
                        topology_handles[island_id],
                        topology_ids[island_id],
                        self.params,
                        signal_actor,
                    )
                    for island_id, island in enumerate(islands[1:], start=1)
                ]
            )
        )

        ready_islands = ray.get(
            [computation.ready.remote() for computation in computations],
            timeout=self.params.actor_startup_timeout,
        )
        if sorted(ready_islands) != list(range(self.params.island_count)):
            raise RuntimeError("Not every Computation actor became ready")

        print("po computation.extend")

        aaa = [computation.start.remote() for computation in computations]
        print ("przed return") #,aaa)

        return aaa
