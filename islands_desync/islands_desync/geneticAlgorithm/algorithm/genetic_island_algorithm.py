import json
import gzip
import hashlib
import os
import random
import statistics
import time
import copy
from datetime import datetime
from math import trunc
from typing import List, TypeVar
from dataclasses import asdict

import numpy as np
import pandas as pd
from jmetal.algorithm.singleobjective.genetic_algorithm import GeneticAlgorithm
from jmetal.config import store
from jmetal.core.operator import Crossover, Mutation, Selection
from jmetal.core.problem import Problem
from jmetal.core.solution import Solution
from jmetal.util.evaluator import Evaluator
from jmetal.util.generator import Generator
from jmetal.util.termination_criterion import TerminationCriterion

from ...islands.core.Migration import Migration, MigrationInfo
from ..solution.float_island_solution import FloatIslandSolution
from ..utils.decision_variables import decision_variables
from ..utils import (
    boxPloter,
    controller,
    dataForPopulationPloter,
    datetimer,
    distance,
    filename,
    fileslister,
    logger,
    ploter,
    result_saver,
    tsne,
)

# import winsound


# from islands_desync.geneticAlgorithm.utils import dirCreator
# from islands_desync.geneticAlgorithm.utils import checker

S = TypeVar("S")
R = TypeVar("R")


class GeneticIslandAlgorithm(GeneticAlgorithm):
    def __init__(
        self,
        problem: Problem,
        population_size: int,
        offspring_population_size: int,
        mutation: Mutation,
        crossover: Crossover,
        selection: Selection,
        migration_interval: int,
        number_of_islands: int,
        number_of_emigrants: int,
        island: int,
        want_create_boxplot: bool,
        want_create_plot: bool,
        want_save_migrants_in_txt: bool,
        want_save_diversity_when_improvement: bool,
        want_tsne_to2: bool,
        want_tsne_to3: bool,
        want_diversity_to_console: bool,
        want_run_end_communications: bool,
        type_of_connection: str,
        migrant_selection_type: str,
        migrant_acceptation_strategy: str,
        how_many_data_intervals: int,
        plot_population_interval: int,
        par_date: str,
        par_time: str,
        wyspWRun: int,
        seria: int,
        migration: Migration,
        topology: str,
        termination_criterion: TerminationCriterion = store.default_termination_criteria,
        population_generator: Generator = store.default_generator,
        population_evaluator: Evaluator = store.default_evaluator,
    ):
        super(GeneticIslandAlgorithm, self).__init__(
            problem,
            population_size,
            offspring_population_size,
            mutation,
            crossover,
            selection,
            termination_criterion,
            population_generator,
            population_evaluator,
        )

        self.migration = migration
        self.min_fitness_per_evaluation = dict()
        self.migration_interval = migration_interval
        self.number_of_emigrants = number_of_emigrants
        self.number_of_islands = number_of_islands
        self.island = island
        self.last_migration_evolution = 0

        self.want_create_boxplot = want_create_boxplot
        self.want_create_plot = want_create_plot
        self.want_save_migrants_in_txt = want_save_migrants_in_txt
        self.want_save_diversity_when_improvement = want_save_diversity_when_improvement
        self.want_tsne_to2 = want_tsne_to2
        self.want_tsne_to3 = want_tsne_to3
        self.want_diversity_to_console = want_diversity_to_console
        self.want_run_end_communications = want_run_end_communications
        self.type_of_connection = type_of_connection
        self.migrant_selection_type = migrant_selection_type
        self.migrant_acceptation_strategy = migrant_acceptation_strategy
        self.how_many_data_intervals = how_many_data_intervals

        self.data_interval = round(
            self.termination_criterion.max_evaluations // self.how_many_data_intervals
        )
        self.plot_population_interval = plot_population_interval
        self.par_date = par_date
        self.par_time = par_time
        self.wyspWRun = wyspWRun
        self.seria = (seria,)
        (seriaa,) = self.seria
        self.seria = seriaa
        self.topology=topology

        self.ts1 = time.time()

        self.last_step = trunc(
            (self.termination_criterion.max_evaluations - self.population_size)
            / self.offspring_population_size
        )

        # self.migrant_selection_type=
        # "random", "maxDistance", "best", "worst"

        self.dta = datetimer.Datetimer(self, self.want_run_end_communications)
        self.czasStart = self.dta.teraz()
        self.dist = distance.Distance()

        # tablica do statystyk migracji z wysp
        # 0 - ile ogółem emigrowało z danej wyspy
        # 1 - ile z tych emigrantów było lepszych niż aktualnie najlepszy osobnik na wyspie docelowej
        # t[0][idx] - ile ogółem emigrowało z wyspy idx
        # t[1][idx] - ile z tych emigrantów było lepszych niż aktualnie najlepszy osobnik na wyspie docelowej
        self.tab_jakosc_migracji_z_wysp = [[0 for _ in range (self.number_of_islands)], 
                                           [0 for _ in range(self.number_of_islands)]]

        # SCIEZKA I NAZWA PLIKOW
        self.fileName = filename.Filename(self, self.want_run_end_communications)
        self.problem_log_size = getattr(self.problem, "number_of_bits", self.problem.number_of_variables)
        if (
            self.problem.get_name()[0:4] == "Labs"
        ):  # <----       todo: LABS i problemy gdzie szukamy max
            self.Fname = self.fileName.getname(
                par_date + "_" + par_time,
                self.problem.get_name()[0:4],
                self.problem_log_size, # usun ()
                "",
                self.island,
                self.number_of_islands,
                self.population_size,
                self.offspring_population_size,
                self.termination_criterion.max_evaluations,
            )
        else:
            self.Fname = self.fileName.getname(
                par_date + "_" + par_time,
                self.problem.get_name()[0:4],
                self.problem_log_size, #usun ()
                "",
                self.island,
                self.number_of_islands,
                self.population_size,
                self.offspring_population_size,
                self.termination_criterion.max_evaluations,
            )

        self.path = self.fileName.getpath(
            self.par_date,
            self.problem.get_name()[0:4],
            self.problem_log_size, #usun ()
            self.par_time,
            self.number_of_islands,
            self.migrant_selection_type[0],
            self.topology[0],
            #"k",
            self.migration_interval,
            self.number_of_emigrants,
        )
        self.fullPath = self.path + "/" + self.Fname
        if self.island == 0:
            print("=== isl:", self.island, " === T O P O L O G Y ", self.topology)
            print("=== ACCEPT-STRATEGY ", self.migrant_acceptation_strategy)


        #KATALOG NA REZULTATY
        if self.island == 0:
            os.makedirs(self.path)
            if self.want_run_end_communications:
                print(
                    "\n\n\n                          The new directory is created! by island: "
                    + str(self.island)
                    + "\n\n\n"
                )
        # else:
        #     while not (os.path.exists(self.path)):
        #         print("w" + str(self.island) + " waits")
        #         time.sleep(1)


        # TWORZENIE TEGO PLIKU POWODUJE BŁęDY
        # self.logfile = logger.Logger(
        #     self.path + "/W" + str(self.island) + " log",
        #     self,
        #     self.want_run_end_communications,
        # )

        if self.island == 0:
            self.resultfile = logger.Logger(
                self.path + "/___RESULT", self, self.want_run_end_communications
            )
            self.winnerfile = logger.Logger(
                self.path + "/___WINNER", self, self.want_run_end_communications
            )

        self.ctrl = controller.Controller(
            self.path, self.island, self.want_run_end_communications
        )

        self.uzup = ""
        self.step_num = 0
        self.lastBest = 50000.0
        # self.lastBest = 0.0 dla LABS

        self.emigrations_history: dict[int, MigrationInfo] = {}

        self.tab_detailed_population = {}

        self.tab_all_steps_Y = {}

        self.tab_jump_best_result_and_all = {}
        self.tab_jump_ind = 0

        self.tab_diversity = {}

        self.nowi = False
        self.bylLog = False

        # Research telemetry is buffered in actor memory and compressed once at
        # the end.  Synchronous per-message filesystem writes would perturb the
        # very migration delays we want to measure.
        self.metrics_schema_version = 1
        self.metrics_started_timestamp_unix = time.time()
        self.metrics_started_monotonic = time.monotonic()
        self.effect_horizon_steps = int(
            os.environ.get("ISLANDS_EFFECT_HORIZON_STEPS", "25")
        )
        self.processed_migration_events: list[dict] = []
        self._migration_survival_watch: dict[str, dict] = {}
        self._current_step_migration_events: list[dict] = []
        self.fitness_history_full: list[dict] = []
        self.best_fitness_seen = None
        self.metrics_counters = {
            "receive_calls": 0,
            "empty_receive_calls": 0,
            "received_before_filter": 0,
            "accepted_by_filter": 0,
            "rejected_by_filter": 0,
            "survived_replacement": 0,
        }

    def __str__(self):
        return "genetic_island_algorithm"

    def __del__(self):
        if self.want_run_end_communications:
            print("koniec genetic_island_algorithm")

    # MIGRATION SECTION  -----------------------------------------------------------
    def get_individuals_to_migrate(
        self, population: List[S], number_of_emigrants: int
    ) -> List[S]:
        if len(population) < number_of_emigrants:
            raise ValueError("Population is too small")

        # "random", "maxDistance", "best", "worst"
        if self.migrant_selection_type == "maxDistance":
            emigrantsnum = self.dist.maxDistanceTab(
                population, self.number_of_emigrants
            )
            emigrants = [population[i] for i in emigrantsnum]
        elif self.migrant_selection_type == "best":
            emigrantsnum = self.dist.bestTab(population, self.number_of_emigrants)
            emigrants = [population[i] for i in emigrantsnum]
        elif self.migrant_selection_type == "worst":
            # if self.step_num<100:
            #    print("worst - wyspa - step - eval",self.island,self.step_num,self.evaluations)
            emigrantsnum = self.dist.worstTab(population, self.number_of_emigrants)
            emigrants = [population[i] for i in emigrantsnum]
        else:
            emigrants = [
                population[random.randrange(len(population))]
                for _ in range(0, number_of_emigrants)
            ]
        return emigrants

    def migrate_individuals(self):
        if self.evaluations - self.last_migration_evolution >= self.migration_interval:
            try:
                individuals_to_migrate = self.get_individuals_to_migrate(
                    self.solutions, self.number_of_emigrants
                )
                self.last_migration_evolution = self.evaluations
            except ValueError as ve:
                print(
                    "-- ValueError -- migrate individuals  --",
                    ve.__str__(),
                    " ",
                    self.island,
                    " ",
                    self.step_num,
                )
                return

            self.migration.migrate_individuals(
                individuals_to_migrate,
                self.step_num,
                self.island,
                time.time(),
                self.island,
                self.evaluations,
                float(self.lastBest),
            )

    # TODO: Fix SAS selection
    # def _get_island_quality(self, island_idx: int):
    #     if self.tab_jakosc_migracji_z_wysp[0][island_idx] == 0:
    #         return 0
    #     return self.tab_jakosc_migracji_z_wysp[1][island_idx] / self.tab_jakosc_migracji_z_wysp[0][island_idx]

    # def _sas_selection_strategy(
    #     self, proc: float = 80
    # ) -> list[bool]:
    #     island_count = len(self.tab_jakosc_migracji_z_wysp[1])

    #     tab_nie_zero = []
    #     for j in range(island_count):
    #         if self.tab_jakosc_migracji_z_wysp[1][j] != 0:
    #             tab_nie_zero.append(self._get_island_quality(j))
    #     if len(tab_nie_zero) == 0:
    #         tab_nie_zero.append(0)

    #     percentyl = np.percentile(
    #         tab_nie_zero, proc
    #     )

    #     def _select_island(index: int, percentyl: float):
    #         if self.tab_jakosc_migracji_z_wysp[0][index] == 0:
    #             return False
    #         return self._get_island_quality(index) >= percentyl

    #     return [_select_island(i, percentyl) for i in range(island_count)]

    def parse_acceptation_strategy(self):
        strategy = self.migrant_acceptation_strategy
        duplicate_after_filter = False
        param = None

        if strategy.startswith("dup_"):
            duplicate_after_filter = True
            strategy = strategy[len("dup_"):]

        if ":" in strategy:
            strategy, param_text = strategy.split(":", 1)
            param = int(param_text)

        return strategy, param, duplicate_after_filter

    def filter_new_individuals(
        self, 
        strategy: str,
        param: int,
        new_individuals: list[FloatIslandSolution],
        emigration_at_step_num: MigrationInfo
    ) -> tuple[list[FloatIslandSolution], MigrationInfo]:
        imigr_fitnsesses = emigration_at_step_num.fitnesses
        imigr_iterations = emigration_at_step_num.iteration_numbers

        individuals_count = len(new_individuals)

        if individuals_count == 0:
            empty_emigration_info = MigrationInfo(
                step=emigration_at_step_num.step,
                ev=emigration_at_step_num.ev,
                iteration_numbers=[],
                timestamps=[],
                src_islands=[],
                fitnesses=[],
                events=[],
                fetch=emigration_at_step_num.fetch,
            )
            return [], empty_emigration_info

        selected_imigrant_mask = [False] * individuals_count

        if strategy == "plain":
            selected_imigrant_mask = [True] * individuals_count
        elif strategy == "better":
            for i in range(individuals_count):
                if imigr_fitnsesses[i] < self.lastBest:
                    selected_imigrant_mask[i] = True
        elif strategy == "newer": # akceptuj tylko imigrantów, którzy są "nowsi" niż aktualna iteracja
            for i in range(individuals_count):
                delay = imigr_iterations[i] - self.step_num
                if delay >= 0:
                    selected_imigrant_mask[i] = True
        elif strategy == "older": # akceptuj tylko imigrantów, którzy są tak "starzy" jak lub "starsi" niż aktualna iteracja
            for i in range(individuals_count):
                delay = imigr_iterations[i] - self.step_num
                if delay <= 0:
                    selected_imigrant_mask[i] = True
        elif strategy == "oldest": # akceptuj tylko imigrantów, którzy są "starsi" niż aktualna iteracja
            for i in range(individuals_count):
                delay = imigr_iterations[i] - self.step_num
                if delay < 0:
                    selected_imigrant_mask[i] = True
        elif strategy == "stochastic":
            epsilon = 0.01 if param is None else max(0.0, min(1.0, param / 100.0))
            delays = [iteration - self.step_num for iteration in imigr_iterations]
            min_delay = min(delays)
            max_delay = max(delays)

            for i, delay in enumerate(delays):
                if max_delay == min_delay:
                    normalized_probability = 1.0
                else:
                    normalized_probability = (delay - min_delay) / (max_delay - min_delay)
                accept_probability = epsilon + normalized_probability * (1.0 - epsilon)
                if random.random() < accept_probability:
                    selected_imigrant_mask[i] = True
        elif strategy == "rejectTooOld": # odrzucaj imigrantów, którzy są starsi niż K
            if param is None:
                param = self.migration_interval * 2
            for i in range(individuals_count):
                delay = imigr_iterations[i] - self.step_num
                if delay >= -param:
                    selected_imigrant_mask[i] = True
        elif strategy == "window":
            if param is None:
                param = self.migration_interval
            for i in range(individuals_count):
                delay = imigr_iterations[i] - self.step_num
                if abs(delay) <= param:
                    selected_imigrant_mask[i] = True
        else:
            raise ValueError(f"Unknown migrant acceptance strategy: {self.migrant_acceptation_strategy}")


        # if "SAS" in strategy:
        #     sas_islands_mask = self._sas_selection_strategy(proc=80)
        #     for island_idx in range(len(imigr_src_islands)):
        #         if sas_islands_mask[imigr_src_islands[island_idx]]:
        #             selected_imigrant_mask[island_idx] = True

        filtered_indices = [
            i for i in range(individuals_count)
            if selected_imigrant_mask[i]
        ]
        
        filtered_emigration_info = MigrationInfo(
            step=emigration_at_step_num.step,
            ev=emigration_at_step_num.ev,
            iteration_numbers=[emigration_at_step_num.iteration_numbers[i] for i in filtered_indices],
            timestamps=[emigration_at_step_num.timestamps[i] for i in filtered_indices],
            src_islands=[emigration_at_step_num.src_islands[i] for i in filtered_indices],
            fitnesses=[emigration_at_step_num.fitnesses[i] for i in filtered_indices],
            events=[copy.deepcopy(emigration_at_step_num.events[i]) for i in filtered_indices]
            if emigration_at_step_num.events
            else [],
            fetch=emigration_at_step_num.fetch,
        )

        return [new_individuals[i] for i in filtered_indices], filtered_emigration_info
    
    def duplicate_individuals(self, 
                              individuals: list[FloatIslandSolution], 
                              emigration_info: MigrationInfo,
                              target_count: int) -> tuple[list[FloatIslandSolution], MigrationInfo]:
        # Randomly duplicate individuals until we have target_count individuals.
        # The algorithm is a minimization algorithm, so lower fitness is better.

        if len(individuals) == 0:
            return [], emigration_info

        if len(individuals) >= target_count:
            emigration_info.iteration_numbers = emigration_info.iteration_numbers[:target_count]
            emigration_info.timestamps = emigration_info.timestamps[:target_count]
            emigration_info.src_islands = emigration_info.src_islands[:target_count]
            emigration_info.fitnesses = emigration_info.fitnesses[:target_count]
            emigration_info.events = emigration_info.events[:target_count]
            return copy.deepcopy(individuals[:target_count]), emigration_info

        fitnesses = [ind.objectives[0] for ind in individuals]
        max_fitness = max(fitnesses)

        if max_fitness == 0:
            probabilities = [1 / len(individuals)] * len(individuals)
        else:
            probabilities = [1 - (fit / max_fitness) for fit in fitnesses]
            total_prob = sum(probabilities)

            if total_prob <= 0:
                probabilities = [1 / len(individuals)] * len(individuals)
            else:
                probabilities = [p / total_prob for p in probabilities]

        duplicated_individuals = copy.deepcopy(individuals)

        while len(duplicated_individuals) < target_count:
            selected_index = random.choices(range(len(individuals)), weights=probabilities, k=1)[0]
            duplicated_individuals.append(copy.deepcopy(individuals[selected_index]))
            emigration_info.iteration_numbers.append(emigration_info.iteration_numbers[selected_index])
            emigration_info.timestamps.append(emigration_info.timestamps[selected_index])
            emigration_info.src_islands.append(emigration_info.src_islands[selected_index])
            emigration_info.fitnesses.append(emigration_info.fitnesses[selected_index])
            if emigration_info.events:
                duplicate_event = copy.deepcopy(emigration_info.events[selected_index])
                duplicate_event["copy_of_event_id"] = duplicate_event.get("event_id")
                duplicate_event["local_copy_index"] = len(duplicated_individuals) - 1
                duplicate_event["is_local_duplicate"] = True
                emigration_info.events.append(duplicate_event)

        return duplicated_individuals, emigration_info

    def add_new_individuals(self):
        new_individuals, emigration_at_step_num = self.migration.receive_individuals(
            self.step_num, self.evaluations
        )

        initial_length = len(new_individuals)
        self.metrics_counters["receive_calls"] += 1
        self.metrics_counters["received_before_filter"] += initial_length
        if initial_length == 0:
            self.metrics_counters["empty_receive_calls"] += 1

        if not emigration_at_step_num.events and initial_length:
            emigration_at_step_num.events = [
                {
                    "schema_version": 0,
                    "event_id": f"legacy:{self.island}:{self.step_num}:{index}",
                    "batch_id": None,
                    "source_island": emigration_at_step_num.src_islands[index],
                    "source_step": emigration_at_step_num.iteration_numbers[index],
                    "source_evaluations": None,
                    "fitness_at_send": emigration_at_step_num.fitnesses[index],
                    "send_timestamp_unix": emigration_at_step_num.timestamps[index],
                }
                for index in range(initial_length)
            ]
        for index, event in enumerate(emigration_at_step_num.events):
            if not event.get("event_id"):
                event["event_id"] = f"legacy:{self.island}:{self.step_num}:{index}"

        strategy, param, duplicate_after_filter = self.parse_acceptation_strategy()

        new_individuals, emigration_info = self.filter_new_individuals(
            strategy, param,
            new_individuals, emigration_at_step_num
        )

        if duplicate_after_filter:
            new_individuals, emigration_info = self.duplicate_individuals(new_individuals, emigration_info, initial_length)

        accepted_event_ids = {
            event.get("event_id") for event in emigration_info.events
        }
        decision_timestamp = time.time()
        process_events = []
        for event in emigration_at_step_num.events:
            process_event = copy.deepcopy(event)
            event_id = process_event.get("event_id")
            accepted = event_id in accepted_event_ids
            source_step = process_event.get("source_step")
            send_timestamp = process_event.get("send_timestamp_unix")
            process_event.update(
                {
                    "record_type": "process",
                    "processed": True,
                    "process_status": "accepted" if accepted else "rejected_by_filter",
                    "destination_island": self.island,
                    "process_step": self.step_num,
                    "process_evaluations": self.evaluations,
                    "process_timestamp_unix": decision_timestamp,
                    "filter_decision_timestamp_unix": decision_timestamp,
                    "recipient_best_before": float(self.lastBest),
                    "recipient_population_size_before_candidates": len(
                        self.solutions
                    ),
                    "migrant_selection_strategy": self.migrant_selection_type,
                    "acceptance_strategy": self.migrant_acceptation_strategy,
                    "accepted_by_filter": accepted,
                    "rejection_reason": None
                    if accepted
                    else f"rejected_by_{strategy}",
                    "added_to_candidates": accepted,
                    "replacement_considered": accepted,
                    "survived_replacement": None if accepted else False,
                    "survived_h_steps": None,
                    "signed_delay_steps": (
                        source_step - self.step_num
                        if source_step is not None
                        else None
                    ),
                    "age_steps": (
                        max(0, self.step_num - source_step)
                        if source_step is not None
                        else None
                    ),
                    "lead_steps": (
                        max(0, source_step - self.step_num)
                        if source_step is not None
                        else None
                    ),
                    "send_to_process_latency_ms": (
                        (decision_timestamp - send_timestamp) * 1000.0
                        if send_timestamp is not None
                        else None
                    ),
                    "strictly_better_than_recipient_best_before": (
                        process_event.get("fitness_at_send") < self.lastBest
                    ),
                    "better_or_equal_to_recipient_best_before": (
                        process_event.get("fitness_at_send") <= self.lastBest
                    ),
                }
            )
            process_events.append(process_event)

        accepted_count = sum(
            1 for event in process_events if event["accepted_by_filter"]
        )
        self.metrics_counters["accepted_by_filter"] += accepted_count
        self.metrics_counters["rejected_by_filter"] += initial_length - accepted_count
        self._current_step_migration_events.extend(process_events)

        for individual, event in zip(new_individuals, emigration_info.events):
            event_id = event.get("event_id")
            try:
                individual.migration_event_id = event_id
                individual.migration_process_step = self.step_num
            except (AttributeError, TypeError):
                pass

        for event in emigration_info.events:
            if event.get("is_local_duplicate"):
                duplicate_event = copy.deepcopy(event)
                duplicate_event.update(
                    {
                        "record_type": "local_duplicate",
                        "destination_island": self.island,
                        "process_step": self.step_num,
                        "accepted_by_filter": True,
                        "added_to_candidates": True,
                    }
                )
                self._current_step_migration_events.append(duplicate_event)

        imigr_src_islands = emigration_info.src_islands
        imigr_fitnsesses = emigration_info.fitnesses

        # update migration stats
        for imigr_ind in range(len(imigr_src_islands)):
            self.tab_jakosc_migracji_z_wysp[0][imigr_src_islands[imigr_ind]] += 1
            if imigr_fitnsesses[imigr_ind] < self.lastBest:
                self.tab_jakosc_migracji_z_wysp[1][imigr_src_islands[imigr_ind]] += 1

        if len(new_individuals) > 0:
            self.nowi = True
            emigration_info.destinTimestamp = time.time()
            emigration_info.destinMaxFitness = self.lastBest
            self.emigrations_history[self.step_num] = emigration_info
            self.solutions.extend(list(new_individuals))

    def _survivor_event_ids(self) -> set[str]:
        return {
            event_id
            for solution in self.solutions
            for event_id in [getattr(solution, "migration_event_id", None)]
            if event_id is not None
        }

    def finalize_current_migration_events_after_replacement(self):
        survivor_ids = self._survivor_event_ids()
        replacement_timestamp = time.time()
        recipient_best_after = float(self.solutions[0].objectives[0])
        for event in self._current_step_migration_events:
            if event.get("record_type") != "process":
                self.processed_migration_events.append(event)
                continue
            if not event.get("accepted_by_filter"):
                self.processed_migration_events.append(event)
                continue

            event_id = event.get("event_id")
            survived = event_id in survivor_ids
            event["survived_replacement"] = survived
            event["replacement_observed_step"] = self.step_num
            event["replacement_timestamp_unix"] = replacement_timestamp
            event["recipient_best_after_replacement"] = recipient_best_after
            event["recipient_improvement_after_replacement"] = (
                event["recipient_best_before"] - recipient_best_after
            )
            event["recipient_population_size_after_replacement"] = len(
                self.solutions
            )
            if survived:
                self.metrics_counters["survived_replacement"] += 1
                if self.effect_horizon_steps > 0:
                    event["survival_deadline_step"] = (
                        self.step_num + self.effect_horizon_steps
                    )
                    self._migration_survival_watch[event_id] = event
                else:
                    event["survived_h_steps"] = True
                    event["survival_observation_complete"] = True
                    self.processed_migration_events.append(event)
            else:
                event["survived_h_steps"] = False
                event["survival_observation_complete"] = True
                event["survival_observed_steps"] = 0
                self.processed_migration_events.append(event)
        self._current_step_migration_events = []
        self.update_migration_survival_watch()

    def update_migration_survival_watch(self):
        survivor_ids = self._survivor_event_ids()
        completed = []
        observation_timestamp = time.time()
        for event_id, event in self._migration_survival_watch.items():
            process_step = event["process_step"]
            deadline = event["survival_deadline_step"]
            if event_id not in survivor_ids:
                event["survived_h_steps"] = False
                event["survival_observation_complete"] = True
                event["survival_observed_steps"] = max(
                    0, self.step_num - process_step
                )
                event["survival_observed_timestamp_unix"] = observation_timestamp
                event["recipient_best_at_survival_observation"] = float(
                    self.solutions[0].objectives[0]
                )
                completed.append(event_id)
            elif self.step_num >= deadline:
                event["survived_h_steps"] = True
                event["survival_observation_complete"] = True
                event["survival_observed_steps"] = self.effect_horizon_steps
                event["survival_observed_timestamp_unix"] = observation_timestamp
                event["recipient_best_at_survival_observation"] = float(
                    self.solutions[0].objectives[0]
                )
                completed.append(event_id)
        for event_id in completed:
            self.processed_migration_events.append(
                self._migration_survival_watch.pop(event_id)
            )

    def flush_incomplete_survival_watch(self):
        survivor_ids = self._survivor_event_ids()
        observation_timestamp = time.time()
        for event_id, event in self._migration_survival_watch.items():
            event["survived_h_steps"] = None
            event["survival_observation_complete"] = False
            event["present_at_end_of_run"] = event_id in survivor_ids
            event["survival_observed_steps"] = max(
                0, self.step_num - event["process_step"]
            )
            event["survival_observed_timestamp_unix"] = observation_timestamp
            event["recipient_best_at_survival_observation"] = float(
                self.solutions[0].objectives[0]
            )
            self.processed_migration_events.append(event)
        self._migration_survival_watch = {}

    def record_fitness_snapshot(self, phase: str, evaluations: int):
        values = [float(solution.objectives[0]) for solution in self.solutions]
        if not values:
            return
        current_best = min(values)
        if self.best_fitness_seen is None:
            self.best_fitness_seen = current_best
        else:
            self.best_fitness_seen = min(self.best_fitness_seen, current_best)
        diversity = self.tab_diversity.get(self.step_num, {})
        timestamp = time.time()
        self.fitness_history_full.append(
            {
                "schema_version": 1,
                "island": self.island,
                "phase": phase,
                "step": 0 if phase == "initial_population" else self.step_num,
                "evaluations": int(evaluations),
                "timestamp_unix": timestamp,
                "elapsed_monotonic_seconds": (
                    time.monotonic() - self.metrics_started_monotonic
                ),
                "elapsed_since_migration_measurement_start_seconds": (
                    timestamp - self.migration.start
                    if self.migration.start is not None
                    else None
                ),
                "current_best": current_best,
                "best_so_far": self.best_fitness_seen,
                "population_mean": statistics.fmean(values),
                "population_median": statistics.median(values),
                "population_worst": max(values),
                "population_std_ddof_0": statistics.pstdev(values),
                "population_size_observed": len(values),
                "unique_solution_count": diversity.get("y"),
                "minimum_coordinate_std": diversity.get("y2"),
                "mean_coordinate_std": diversity.get("y3"),
            }
        )

    @staticmethod
    def _json_safe(value):
        if isinstance(value, dict):
            return {
                str(key): GeneticIslandAlgorithm._json_safe(item)
                for key, item in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [GeneticIslandAlgorithm._json_safe(item) for item in value]
        if isinstance(value, np.generic):
            return value.item()
        return value

    @staticmethod
    def _write_json_atomic(path: str, value):
        temporary = path + ".tmp"
        with open(temporary, "w", encoding="utf-8") as output:
            json.dump(
                GeneticIslandAlgorithm._json_safe(value),
                output,
                indent=2,
                allow_nan=False,
            )
            output.write("\n")
        os.replace(temporary, path)

    @staticmethod
    def _write_jsonl_gzip_atomic(path: str, records):
        temporary = path + ".tmp"
        with gzip.open(temporary, "wt", encoding="utf-8", compresslevel=6) as output:
            for record in records:
                output.write(
                    json.dumps(
                        GeneticIslandAlgorithm._json_safe(record),
                        separators=(",", ":"),
                        allow_nan=False,
                    )
                )
                output.write("\n")
        os.replace(temporary, path)

    def _metrics_directory(self) -> str:
        return os.path.join(self.path, "metrics", f"island_{self.island:03d}")

    def write_runtime_metrics(self, runtime_metrics: dict):
        metrics_directory = self._metrics_directory()
        os.makedirs(metrics_directory, exist_ok=True)
        self._write_json_atomic(
            os.path.join(metrics_directory, "runtime.json"), runtime_metrics
        )

    def export_research_metrics(self, migration_telemetry: dict, runtime_metrics: dict):
        self.flush_incomplete_survival_watch()
        metrics_directory = self._metrics_directory()
        os.makedirs(metrics_directory, exist_ok=True)
        run_id = f"{self.par_date}_{self.par_time}"

        sent_events = []
        for event in migration_telemetry["sent_events"]:
            sent_events.append(
                {
                    **event,
                    "run_id": run_id,
                    "recording_island": self.island,
                    "migrant_selection_strategy": self.migrant_selection_type,
                    "acceptance_strategy": self.migrant_acceptation_strategy,
                }
            )
        process_events = [
            {
                **event,
                "run_id": run_id,
                "recording_island": self.island,
            }
            for event in (
                self.processed_migration_events
                + migration_telemetry["prefetched_unprocessed_events"]
                + migration_telemetry["queued_unprocessed_events"]
            )
        ]
        migration_events = sent_events + process_events
        migration_events.sort(
            key=lambda event: (
                event.get("send_timestamp_unix") or 0.0,
                event.get("event_id") or "",
                event.get("record_type") or "",
            )
        )
        self._write_jsonl_gzip_atomic(
            os.path.join(metrics_directory, "migration_events.jsonl.gz"),
            migration_events,
        )
        self._write_jsonl_gzip_atomic(
            os.path.join(metrics_directory, "queue_fetches.jsonl.gz"),
            migration_telemetry["queue_fetches"],
        )
        self._write_jsonl_gzip_atomic(
            os.path.join(metrics_directory, "fitness_history.jsonl.gz"),
            self.fitness_history_full,
        )

        best_solution = self.get_result()
        variables = self._json_safe(list(decision_variables(best_solution)))
        canonical_variables = json.dumps(
            variables, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
        final_solution = {
            "schema_version": 1,
            "run_id": run_id,
            "island": self.island,
            "objectives": self._json_safe(list(best_solution.objectives)),
            "variables": variables,
            "variables_sha256": hashlib.sha256(canonical_variables).hexdigest(),
            "variable_count": len(variables),
            "from_island": getattr(best_solution, "from_island", None),
            "from_evaluation": getattr(best_solution, "from_evaluation", None),
            "migration_event_id": getattr(best_solution, "migration_event_id", None),
        }
        self._write_json_atomic(
            os.path.join(metrics_directory, "final_solution.json"), final_solution
        )

        summary = {
            "schema_version": 1,
            "run_id": run_id,
            "island": self.island,
            "effect_horizon_steps": self.effect_horizon_steps,
            "counters": self.metrics_counters,
            "sent_event_records": len(sent_events),
            "process_event_records": sum(
                1 for event in process_events if event.get("record_type") == "process"
            ),
            "local_duplicate_records": sum(
                1
                for event in process_events
                if event.get("record_type") == "local_duplicate"
            ),
            "prefetched_unprocessed_event_records": len(
                migration_telemetry["prefetched_unprocessed_events"]
            ),
            "queued_unprocessed_event_records": len(
                migration_telemetry["queued_unprocessed_events"]
            ),
            "queue_fetch_records": len(migration_telemetry["queue_fetches"]),
            "fitness_snapshot_records": len(self.fitness_history_full),
            "final_solution_variables_sha256": final_solution["variables_sha256"],
        }
        self._write_json_atomic(
            os.path.join(metrics_directory, "summary.json"), summary
        )
        self.write_runtime_metrics(runtime_metrics)

        if self.island == 0:
            data_contract = {
                "schema_version": 1,
                "format": "IslandsEA research telemetry",
                "storage": "one metrics/island_NNN directory per island",
                "event_identity": "event_id is unique within run_id",
                "event_record_types": {
                    "send": "one source-side record per transmitted individual",
                    "process": (
                        "one destination-side terminal record: processed, final prefetch, "
                        "or queued at end"
                    ),
                    "local_duplicate": "optional destination-only copy made by dup_* acceptance",
                },
                "delay_definition": "source_step - process_step (negative means stale/older)",
                "time_fields": "Unix seconds; queue_residence_ms uses destination-process monotonic clock",
                "files": {
                    "migration_events.jsonl.gz": "send, process and optional local_duplicate records",
                    "queue_fetches.jsonl.gz": "one record per asynchronous queue fetch",
                    "fitness_history.jsonl.gz": "initial and per-step population summaries",
                    "final_solution.json": "final genotype, objectives and canonical-variable SHA-256",
                    "runtime.json": "actor placement, phases, evaluations and end queue state",
                    "summary.json": "record counts and instrumentation counters",
                },
                "legacy_outputs_preserved": True,
                "null_semantics": (
                    "null means not observable/not applicable/incomplete; it must not be "
                    "coerced to false or zero"
                ),
                "survival_semantics": (
                    "survival tracks the exact migrant tag retained in the population; "
                    "offspring do not inherit it, and incomplete horizons at run end "
                    "are null rather than false"
                ),
            }
            self._write_json_atomic(
                os.path.join(self.path, "metrics", "data_contract.json"),
                data_contract,
            )

    def wytnij(self, lancuchZnakow):
        return lancuchZnakow.replace("\n", "")

    def paramJson(self):
        # fix race condition where multiple islands try to write param.json at the same time at the end of the run
        if self.island != 0:
            return

        self.uzup = self.uzupParamLog()
        jsn = result_saver.Result_Saver(
            self.path + "/param", self, self.want_run_end_communications
        )
        results = {
            "problem": self.problem.get_name(), #
            "number of variables": str(self.problem_log_size), #
            "termination criterion": str(self.termination_criterion.__str__()),
            "number of eval": str(self.termination_criterion.max_evaluations),
            "population size": str(self.population_size),
            "offspring population size": str(self.offspring_population_size),
            "number of islands": str(self.number_of_islands),
            "island": str(self.island),
            "type_of_connection": str(self.type_of_connection),
            "migrant_selection_type": self.migrant_selection_type,
            "migrant_acceptation_strategy": self.migrant_acceptation_strategy,
            "migration interval": str(self.migration_interval),
            "number of emigrants": str(self.number_of_emigrants),
            "how_many_data_intervals": str(self.how_many_data_intervals),
            "data interval": str(self.data_interval),
            "plot population interval": str(self.plot_population_interval),
            "min fitness per evaluation": str(self.min_fitness_per_evaluation),
            "want_create_boxplot": str(self.want_create_boxplot),
            "want_create_plot": str(self.want_create_plot),
            "want_save_migrants_in_txt": str(self.want_save_migrants_in_txt),
            "want_save_diversity_when_improvement": str(
                self.want_save_diversity_when_improvement
            ),
            "want_tsne_to2": str(self.want_tsne_to2),
            "want_tsne_to3": str(self.want_tsne_to3),
            "want_diversity_to_console": str(self.want_diversity_to_console),
            "want_run_end_communications": str(self.want_run_end_communications),
            "last_step": str(self.last_step),
            "operators": self.wytnij(self.uzup),
        }

        if hasattr(self, "active_operators"):
            results["active_operators"] = self.active_operators

        # commented out because rabbitmq_delays was moved out of this class
        # if self.number_of_islands > 1:
        #     results["rabbitmq_delays: "] = str(self.migration.rabbitmq_delays)
        jsn.saveJson(results)

    def uzupParamLog(
        self,
    ):  # dodaje info o krzyzowaniu, mutacji i selekcji z run_algorithm.py (tekst)
        douzup = ""
        wlaczone = False
        file1 = open("./islands_desync/geneticAlgorithm/run_algorithm.py", "r")
        lines = file1.readlines()
        for line in lines:
            obciety = line.strip()
            if obciety.startswith("###"):
                wlaczone = not wlaczone
            if wlaczone:
                if (len(obciety) > 0) and (not obciety.startswith("#")):
                    douzup += obciety + "\n"
        file1.close()
        return douzup

    def saveTabsAndRuningTimeInLogFile(self):
        self.logfile.writeLog(
            "\n\nczas trwania: "
            + str(self.dta.teraz() - self.czasStart)
            + "\nlast step: "
            + str(self.step_num),
            self,
        )
        self.bylLog = True

    # CSV SECTION  -----------------------------------------------------------
    def createCsvForThisStep(
        self, poprawa
    ):  # OBRAZ GENERACJI W TYM MOMENCIE ZRZUT I RYSUNEK
        osobniki = []
        for solut in range(len(self.solutions)):
            lista = []
            for value in decision_variables(self.solutions[solut]):
                lista.append(value)
            osobniki.append(lista)

        dataframeBig = pd.DataFrame(osobniki)

        if poprawa:
            dataframeBig.to_csv(
                self.path
                + "/poprawa/poprawa step"
                + str(self.step_num)
                + " w"
                + str(self.island)
                + " dim__"
                + str(self.problem_log_size) #usun ()
                + ".csv"
            )
        else:
            # print("DF ",len(dataframeBig))
            dataframeBig.to_csv(
                self.path
                + "/diversity-space/array step"
                + str(self.step_num)
                + " w"
                + str(self.island)
                + " dim_"
                + str(self.problem_log_size) # usun ()
                + ".csv"
            )

    def createCsvWithTsne(self):
        fl = fileslister.FilesLister("qq", False)
        if self.want_tsne_to2 or self.want_tsne_to3:
            listOfFiles = fl.listFilesExtensionLike(
                self.path + "/diversity-space/",
                str(self.problem_log_size) + ".csv", # brak ()

            )
            tsneA = tsne.Tsne()
            for i in range(len(listOfFiles)):
                if self.want_tsne_to2:
                    tsneA.createTsne(listOfFiles[i], 2)
                if self.want_tsne_to3:
                    tsneA.createTsne(listOfFiles[i], 3)

    # TAB SECTION  -----------------------------------------------------------
    def fitnessNow(self):
        fitness_osobnikow = []
        for ind in range(self.solutions.__len__()):  # self.population_size
            fitness_osobnikow.append(self.solutions[ind].objectives[0])
        return fitness_osobnikow

    def saveXiYiFittnessWhileJump(self):
        self.tab_jump_best_result_and_all[self.tab_jump_ind] = {
            "stepX": self.step_num,
            "fitness": self.lastBest,
            "all_fitn": self.fitnessNow(),
        }
        # self.tabelkaY.append(-self.lastBest) #todo for LABS
        self.tab_jump_ind += 1

    def saveDetailedPopulationDescriptionForThisStepInTab(
        self,
    ):  # OBRAZ GENERACJI W TYM MOMENCIE ZRZUT I RYSUNEK
        osobniki = []
        for solut in range(len(self.solutions)):
            lista = []
            for value in decision_variables(self.solutions[solut]):
                lista.append(value)
            osobniki.append(lista)
        self.tab_detailed_population[self.step_num] = osobniki

    # DIVERSITY TAB SECTION -----------------------------------------------------------
    def savePopulationDiversitiesThreeOfKindForThisStepInTab(self):
        setPopul = set()
        for i in range(len(self.solutions)):
            solution = decision_variables(self.solutions[i])
            solutionWhole = ""
            for i in range(len(solution)):
                solutionWhole += " " + str(solution[i])
            setPopul.add(solutionWhole)
        lsp = len(setPopul)

        # DIVERSITY LICZONE ZE STD ODCHYLENIA - Min i Sredni
        listaaa = []
        for i in range(self.solutions.__len__()):  # population_size
            listaaa.append(decision_variables(self.solutions[i]))

        listalTransposed = np.array(listaaa).transpose()
        a, b = distance.Distance.minISrOdchStd(listalTransposed)

        self.tab_diversity[self.step_num] = {"y": lsp, "y2": a, "y3": b}

    # JSON SECTION  -----------------------------------------------------------
    def createEmigrJson(self):
        jsn = result_saver.Result_Saver(
            self.path + "/W" + str(self.island) + " Imigrants",
            self,
            self.want_run_end_communications,
        )
        legacy_history = {}
        for step, info in self.emigrations_history.items():
            record = asdict(info)
            record.pop("events", None)
            record.pop("fetch", None)
            legacy_history[step] = record
        jsn.saveJson(legacy_history)

    def createAllStepsDetailedPopulationJson(self):
        jsn = result_saver.Result_Saver(
            self.path
            + " - W"
            + str(self.island)
            + "every step population details-do step"
            + str(self.step_num),
            self,
            self.want_run_end_communications,
        )
        jsn.saveJson({})
        #jsn.saveJson(self.tab_detailed_population)
        self.tab_detailed_population = {}

    def createAllStepsResultsJson(self):
        jsn = result_saver.Result_Saver(
            self.path + "/resultsEveryStepW" + str(self.island),
            self,
            self.want_run_end_communications,
        )
        jsn.saveJson(self.tab_all_steps_Y)

    def createJumpResultsJson(self):
        jsn = result_saver.Result_Saver(
            self.path + "/W" + str(self.island) + " results jump",
            self,
            self.want_run_end_communications,
        )
        jsn.saveJson(self.tab_jump_best_result_and_all)

    def createJsonAllStepsDiversityJson(self):
        jsn = result_saver.Result_Saver(
            self.path + "/W" + str(self.island) + " set-minOS-srOS-diversity",
            self,
            self.want_run_end_communications,
        )
        jsn.saveJson(self.tab_diversity)

    # PLOT SECTION  -----------------------------------------------------------
    def createResultPlots(self):
        ploter.Ploter(self.want_run_end_communications)
        ploter.Ploter.rysLine_z_tab_dopliku(
            self,
            self.tab_X,
            self.tab_Y,
            self.path + "/results/resultW" + str(self.island),
            self.island,
            "Results of island " + str(self.island),
        )

    def createBoxplot(self):
        if self.want_create_boxplot:
            bp = boxPloter.BoxPloter(self, self.want_run_end_communications)
            bp.makeIslandBoxPlot(
                self.path,
                "W" + str(self.island) + " results " + str(self.data_interval),
                self.island,
                self.data_interval,
                "Fitness diversity of island " + str(self.island),
            )

    def createSpaceDiversityPopulationPlots(self):
        if self.ctrl.isCtrlComplete(self.number_of_islands) and self.ctrl.isEndComplete(
            self.number_of_islands
        ):
            self.readyForCumulativePopulPlot = True

    def writeSummaryResutlToConsoleAndFile(self):
        results = []
        for i in range(self.number_of_islands):
            with open(
                self.path + "/" + "kontrolW" + str(i) + "End.ctrl.txt", "r"
            ) as file:
                data = file.readlines()
                for linia in data:
                    #print("             ", linia, "      ", file.name)
                    #self.resultfile.writeLog(linia + "\n", self)
                    results.append(float(linia))

        average = statistics.mean(results)
        minimal = min(results)
        kt_ile = results.count(minimal)
        kt = results.index(minimal)
        ile_res = len(results)

        self.resultfile.writeLog(str(minimal) + "\n" + str(kt) + "\n\n"
            + " -- -- -- " + self.migrant_selection_type + " MIGRANT SELECTION STRATEGY -- -- --\n"
            + " -- -- -- MIGRANT ACCEPTATION STRATEGY " + self.migrant_acceptation_strategy + " -- -- --\n"
            + " -- -- -- " + self.topology + " TOPOLOGY -- -- -- \n"
            + "-" * 36 + "\n" 
            + "Average result:  " + str(average) + "\n"
            + "-" * 36 + "\n" 
            + "Best result   : " + str(minimal) + "\n" 
            + "Winner island: " + str(kt) + " (this result was reached on : " + str(kt_ile) + "/" + str(self.number_of_islands) + " islands)" 
            + " (number of results taken to avg: "+str(ile_res)+")\n\n",
            self,
        )

        for zz in range(len(results)):
            self.resultfile.writeLog(str(zz)+" "+str(results[zz])+"\n",self)

        self.resultfile.saveLog()

        self.winnerfile.writeLog(str(kt), self)
        self.winnerfile.saveLog()

        print(
            " -- -- -- " + self.migrant_selection_type + " MIGRANT SELECTION STRATEGY -- -- --\n"
            + " -- -- -- MIGRANT ACCEPTATION STRATEGY " + self.migrant_acceptation_strategy + " -- -- --\n"
            + " -- -- -- " + self.topology + " TOPOLOGY -- -- -- \n"
            + "-" * 36 + "\n" 
            + "Average result:  " + str(average) + "\n"
            + "-" * 36 + "\n" 
            + "Best result   : " + str(minimal) + "\n" 
            + "Winner island: " + str(kt) + " (this result was reached on : " + str(kt_ile) + "/" + str(self.number_of_islands) + " islands)" 
            + " (number of results taken to avg: "+str(ile_res)+")\n\n",
        )

        #print("Average result: " + str(average))
        print(
            "\n"
            + " " * 7
            + "* "
            + "*" * 19
            + " *"
            + " " * 7
            + "\n"
            + " " * 7
            + "*** " * 2
            + "THE END"
            + " ***" * 2
            + "\n"
            + " " * 7
            + "* "
            + "*" * 19
            + " *"
            + " " * 7
        )

    # MAIN PART - GENETIC ALGORITHM STEP
    def prepare_step_for_evaluation(self):
        """Run one legacy step up to (but excluding) objective evaluation.

        The CPU path still calls :meth:`step`, which immediately evaluates the
        returned offspring and completes the step.  Athena shards use this
        boundary to batch only objective evaluation while retaining migration,
        selection, reproduction and RNG ordering per logical island.
        """
        self.step_num = self.step_num + 1

        if 1 == self.step_num:



            self.migration.wait_for_all_start()
            #print("=====START=====", self.island)
            ts1 = time.time()
            #fileTime = open(self.path+"/W"+self.island+" czas.txt","a")
            #fileTime.write(str(ts1))
            #fileTime.close()




            self.paramJson()
            self.lastBest = self.solutions[0].objectives[0]
            self.saveXiYiFittnessWhileJump()
            self.saveDetailedPopulationDescriptionForThisStepInTab()
            self.savePopulationDiversitiesThreeOfKindForThisStepInTab()
            self.record_fitness_snapshot("initial_population", self.evaluations)

            # start measuring time
            self.migration.start_time_measure()

        # PRZERYWA JESLI NIE WYSTARTOWAŁY WSZYSTKIE WYSPY
        # if self.step_num==85:
        #     ctrl = controller.Controller(self.path, self.island,self.want_run_end_communications)
        #     if not ctrl.isCtrlComplete(self.number_of_islands):
        #         print("\n\n\n\n !!!!!!!!!!!!!!\n NIE WSZYSTKO WYSTARTOWAŁO \n!!!!!!!!!!!!!!!!!\n\n\n\n")
        #         raise SystemExit

        # ZAMIAST PASKA POSTEPU
        # ZRZUT POPULACJI W ORYG WYMIARZE - create csv - wyłączone
        if self.step_num % self.plot_population_interval == 0 or self.step_num == 1:
            print(
                "step "
                + str(self.step_num)
                + " evaluations "
                + str(self.evaluations)
                + " island "
                + str(self.island)
            )
            """if self.step_num != 1:
                self.createAllStepsDetailedPopulationJson()"""
            # self.createCsvForThisStep(False)

        # MIGRACJE
        self.nowi = False
        if self.number_of_islands > 1:
            self.migrate_individuals()
            # todo: SPR CZY MIGRANT POPRAWIŁ WYNIK WYSPY - best w population[0] > best
            # Empty queues are represented explicitly by RayMigrationPipeline.
            # Any other exception is a real data-loss/actor failure and must
            # fail the SLURM task instead of silently corrupting the experiment.
            self.add_new_individuals()

        """if self.nowi:
            print("Step: "+str(self.step_num)+" eval: "+str(self.evaluations)+" NOWI "+str(self.island))"""

        # KRZYŻOWANIE, MUTOWANIE I SELEKCJA
        mating_population = self.selection(self.solutions)
        offspring_population = self.reproduction(mating_population)
        return offspring_population

    def complete_step_after_evaluation(self, offspring_population):
        """Complete the unchanged legacy step with evaluated offspring."""
        # print("**************************", self.solutions.__len__())

        for i in offspring_population:
            i.from_evaluation = self.evaluations
        self.solutions = self.replacement(
            self.solutions, offspring_population
        )  # todo !!! zobacz GŁĘBIEJ ten replacement
        self.finalize_current_migration_events_after_replacement()
        # print("*********------------*******", self.solutions.__len__())

        # Jeśli W KRZYŻWOANIU I MUTACJI POWSTAŁ LEPSZY
        if not (self.lastBest == self.solutions[0].objectives[0]):
            self.lastBest = self.solutions[0].objectives[0]
            # print("BBB",self.solutions.__len__())
            self.saveXiYiFittnessWhileJump()
            #     self.saveTempResultInLogFile()
            # if self.want_save_diversity_when_improvement:
            #    self.createCsvForThisStep(True) # do katalogu poprawa zrzut populacji, todo: tsne i plot
            # rys populacji w jsonie -> "poprawa step2000 w2 dim__30.json"

        # DLA KAŻDEGO KROKU:
        # RÓŻNORODNOŚĆ POPULACJI - do pliku i ewent na konsolę
        if self.step_num % 50 == 0:
            self.saveDetailedPopulationDescriptionForThisStepInTab()  # w tab_detailed_population
        self.savePopulationDiversitiesThreeOfKindForThisStepInTab()
        evaluations_after_step = min(
            self.termination_criterion.max_evaluations,
            self.evaluations + len(offspring_population),
        )
        self.record_fitness_snapshot("after_replacement", evaluations_after_step)

        self.tab_all_steps_Y[
            self.step_num
        ] = self.lastBest  # BEST FITNESS DLA KAŻDEGO KROKU

        # ZAPISZ DANE CO INTERWAŁ
        """if self.step_num%self.data_interval==0:    # todo: LUB step pierwszy !!! i przenumeruj na wykresach !!!
            self.saveTempResultInTab100()"""

        if self.step_num > self.last_step:
            print("^ ^ ^ ", self.step_num, "last:", self.last_step)

        if (self.last_step - 1 < self.step_num) and not self.bylLog:
            self.migration.end_time_measure()
            self.lastBest = self.solutions[0].objectives[0]
            # print("k o n c o w k a",self.island)
            self.saveXiYiFittnessWhileJump()
            # self.saveTempResultInLogFile()
            # self.saveTempResultInTab100()
            # self.createJsonFromCo100Tab()
            self.createJsonAllStepsDiversityJson()
            self.createJumpResultsJson()
            self.createAllStepsResultsJson()
            # self.saveTabsAndRuningTimeInLogFile()
            tab_procent=[[],[]]
            for ind in range(len(self.tab_jakosc_migracji_z_wysp[0])):
                if self.tab_jakosc_migracji_z_wysp[0][ind]==0:
                    tab_procent[0].append(0)
                    tab_procent[1].append(0)
                else:
                    tab_procent[0].append(self.tab_jakosc_migracji_z_wysp[1][ind] / self.tab_jakosc_migracji_z_wysp[0][ind] * 100)
                    tab_procent[1].append(round( self.tab_jakosc_migracji_z_wysp[1][ind] / self.tab_jakosc_migracji_z_wysp[0][ind] * 100,2))

            #print("RANKING", self.island, self.tab_jakosc_migracji_z_wysp, tab_procent)
            jsonSasiad = result_saver.Result_Saver(self.path + "/W" + str(self.island) + "neighbourRanking", self, self.want_run_end_communications)
            jsonSasiad.saveJson(self.tab_jakosc_migracji_z_wysp)
            jsonSasiad2 = result_saver.Result_Saver(self.path + "/W" + str(self.island) + "neighbourRankingPercent",  self, self.want_run_end_communications)
            jsonSasiad2.saveJson(tab_procent)
            
            #print("RANKING", self.island, self.tab_jakosc_migracji_z_wysp, [(self.tab_jakosc_migracji_z_wysp[1][i] / self.tab_jakosc_migracji_z_wysp[0][i] * 100) for i in range (len(self.tab_jakosc_migracji_z_wysp[0]))])
            print("Koniec" + str(self.island))
            self.ctrl.endOfProcess(
                self.island, self.lastBest
            )  # tworzy plik END.ktrl - KONTROLNY Z WYNIKIEM Z TEJ WYSPY
            # self.createResultPlots()                                 # przebieg fitness z tab i tab100 - ta wyspa
            self.createBoxplot()  # rozkład fitness z jsona - ta wyspa
            # self.createDiversityPlots()                        # przebieg różnorodności populacji z tab_diversityX i Y - ta wyspa
            # tab_diversityYminOdchStd i tab_diversityYsrOdchStd"""
            # self.logfile.saveLog()
            # self.emigrLog.writeTabLog(self.tab_emigrants)
            # self.emigrLog.saveLog()
            self.createEmigrJson()
            # !!!!!!!! self.createAllStepsDetailedPopulationJson()

            # self.readyForCumulativePopulPlot = False
            # if self.island == 0:
            #     while not self.readyForCumulativePopulPlot:
            #         print(
            #             " self.readyForCumulativePopulPlot:",
            #             self.readyForCumulativePopulPlot,
            #         )
            #         time.sleep(1)
            #         # self.createCsvWithTsne() # dla dim>3 robi tsne do dim=2 i 3
            #         # print('\a')
            #         self.createSpaceDiversityPopulationPlots()  # dla każdej wyspy i cumulative - jeśli w jsonie jest True - korzysta z csv z tsne
                    # print('\a')
                # self.createAllIslandsDiversityPlots()
                # print('\a')
                # self.createAllIslandsResultPlot()
                # print('\a')
            ts2 = time.time()
            jsnCzas = result_saver.Result_Saver(self.path+"/W"+str(self.island)+" czas", self, self.want_run_end_communications)
            czas = {"startTimeStamp": self.ts1, "endTimeStamp": ts2, "delta": ts2 - self.ts1}
            jsnCzas.saveJson(czas)
            #fileTime = open(self.path+"/W"+str(self.island)+" czas.txt","a")
            #fileTime.write("Tstart: ")
            #fileTime.write(str(self.ts1))
            #fileTime.write("\nTend:   ")
            #fileTime.write(str(ts2))
            #fileTime.write("\n==================================\nTend-Tstart:    ")
            #tsdelta=ts2-self.ts1
            #fileTime.write(str(tsdelta))
            #fileTime.write("\n")
            #fileTime.write("---")
            #fileTime.write(time.strftime('%H:%M:%S',time.gmtime(tsdelta)))
            #fileTime.write("- - -")
            #fileTime.close()

            self.migration.signal_finish()

            if self.island == 0:
                self.migration.wait_for_finish()
                self.writeSummaryResutlToConsoleAndFile()
                self.createAllStepsDetailedPopulationJson()
                # print('\a')
                # time.sleep(1)
                # print('\a')
                # time.sleep(1)
                # print('\a')
                # time.sleep(0.5)
                # print('\a')
                # time.sleep(0.5)
                # print('\a')
                self.ctrl.endOfWholeProbe(self.seria)

    def step(self):
        """Preserve the historical synchronous CPU step exactly."""
        offspring_population = self.prepare_step_for_evaluation()
        offspring_population = self.evaluate(offspring_population)
        self.complete_step_after_evaluation(offspring_population)

    def update_min_fitness_per_evaluation(self):
        min_fitness = min(self.solutions, key=lambda x: x.objectives[0])
        self.min_fitness_per_evaluation[self.evaluations] = min_fitness.objectives[0]
