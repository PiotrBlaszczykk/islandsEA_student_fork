import time
from abc import ABC, abstractmethod
from jmetal.core.solution import Solution
from dataclasses import dataclass

@dataclass
class MigrationInfo:
    step: int
    ev: int
    iteration_numbers: list[int]
    timestamps: list[float]
    src_islands: list[int]
    fitnesses: list[float]
    destinTimestamp: float | None = None
    destinMaxFitness: float | None = None

class Migration(ABC):
    def __init__(self):
        self.start: float | None = None
        self.end: float | None = None

    @abstractmethod
    def migrate_individuals(
            self, individuals_to_migrate, iteration_number: int, island_number: int
    ):
        pass

    @abstractmethod
    def receive_individuals(
            self, step_num: int, evaluations: int
    ) -> tuple[list[Solution], MigrationInfo]:
        pass

    def start_time_measure(self):
        self.start = time.time()

    def end_time_measure(self):
        self.end = time.time()

    def run_time(self):
        return self.end - self.start

    def wait_for_all_start(self):
        pass

    def wait_for_finish(self):
        pass

    def signal_finish(self):
        pass
