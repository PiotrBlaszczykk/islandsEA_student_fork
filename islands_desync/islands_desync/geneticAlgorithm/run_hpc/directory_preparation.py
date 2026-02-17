import dataclasses
import os
import time

from islands_desync.geneticAlgorithm.utils import filename


@dataclasses.dataclass
class DirectoryPreparation:
    problem: any
    island: int
    number_of_islands: int
    population_size: int
    offspring_population_size: int
    termination_criterion: any
    want_run_end_communications: bool
    par_date: str
    par_time: str
    migrant_selection_type: list
    migration_interval: int
    number_of_emigrants: int

    def create_dirs(self):

        self.fileName = filename.Filename(self, self.want_run_end_communications)

        self.Fname = self.fileName.getname(
            self.par_date + "_" + self.par_time,
            self.problem.name()[0:4],
            self.problem.number_of_variables(),
            "",
            self.island,
            self.number_of_islands,
            self.population_size,
            self.offspring_population_size,
            self.termination_criterion.max_evaluations,
        )

        self.path = self.fileName.getpath(
            self.par_date,
            self.problem.name()[0:4],
            self.problem.number_of_variables(),
            self.par_time,
            self.number_of_islands,
            self.migrant_selection_type[0],
            "k",
            self.migration_interval,
            self.number_of_emigrants,
        )

        os.makedirs(self.path)

