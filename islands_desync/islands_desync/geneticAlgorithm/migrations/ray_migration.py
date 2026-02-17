from typing import Dict, List

import ray

from islands_desync.islands.core.Emigration import Emigration
from islands_desync.islands.core.Migration import Migration
from islands_desync.islands.core.SignalActor import SignalActor


class RayMigration(Migration):
    def __init__(self, islandActor, emigration: Emigration, signal_actor: SignalActor):
        super().__init__()
        self.emigration = emigration
        self.islandActor = islandActor
        self.signal_actor: SignalActor = signal_actor

    def migrate_individuals(
        self, individuals_to_migrate, iteration_number, island_number, ind_timestamp, src_island,
    ):
        # print("Emigracja %s iter: %s" % (island_number, iteration_number))
        for individual in individuals_to_migrate:
            # print("%s: Emigruje %s" % (self.islandActor, individual))
            self.emigration.emigrate((individual, iteration_number, ind_timestamp, src_island, individual.objectives[0]))

    def receive_individuals(
        self, step_num: int, evaluations: int
    ) :
        new_individuals = ray.get(self.islandActor.get_immigrants.remote())

        new_individuals, migrant_iteration_numbers = zip(*new_individuals)

        migration_at_step_num = {
            "step": step_num,
            "ev": evaluations,
            "iteration_numbers": migrant_iteration_numbers,
            "timestamps": ind_timestamp,
            "src_islands": src_island,
            "fitnesses": fitness,
        }

        return list(new_individuals), migration_at_step_num

    def wait_for_all_start(self):
        self.signal_actor.send.remote()
        ray.get(self.signal_actor.wait.remote())

    def wait_for_finish(self):
        ray.get(self.signal_actor.wait.remote("finish"))

    def signal_finish(self):
        self.signal_actor.send.remote("finish")
