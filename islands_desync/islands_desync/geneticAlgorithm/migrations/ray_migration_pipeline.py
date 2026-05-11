from typing import Dict, List

import ray
from jmetal.core.solution import Solution

from islands_desync.islands.core.Migration import MigrationInfo
from islands_desync.geneticAlgorithm.migrations.ray_migration import RayMigration
from islands_desync.islands.core.Emigration import Emigration
from islands_desync.islands.core.SignalActor import SignalActor


class RayMigrationPipeline(RayMigration):
    def __init__(self, islandActor, emigration: Emigration, signal_actor: SignalActor):
        super().__init__(islandActor, emigration, signal_actor)
        self.new_individuals_refs = self.islandActor.get_immigrants.remote()

    def receive_individuals(
        self, step_num: int, evaluations: int
    ) -> tuple[list[Solution], MigrationInfo]:
        new_individuals = ray.get(self.new_individuals_refs)
        self.new_individuals_refs = self.islandActor.get_immigrants.remote()

        new_individuals, migrant_iteration_numbers, ind_timestamps, src_island, fitness = zip(*new_individuals)

        # migration_at_step_num = {
        #     "step": step_num,
        #     "ev": evaluations,
        #     "iteration_numbers": migrant_iteration_numbers,
        #     "timestamps": ind_timestamps,
        #     "src_islands": src_island,
        #     "fitnesses": fitness,
        # }

        migration_at_step_num = MigrationInfo(
            step=step_num,
            ev=evaluations,
            iteration_numbers=list(migrant_iteration_numbers),
            timestamps=list(ind_timestamps),
            src_islands=list(src_island),
            fitnesses=list(fitness),
        )

        return list(new_individuals), migration_at_step_num
