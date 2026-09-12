import json
import os
import random
import numpy as np
from datetime import datetime, timedelta

from jmetal.core.problem import BinaryProblem
from jmetal.operator import BinaryTournamentSelection, BitFlipMutation, SPXCrossover
from jmetal.problem.singleobjective.unconstrained import Rastrigin
from jmetal.problem.singleobjective.unconstrained import Sphere

from jmetal.util.termination_criterion import StoppingByEvaluations

from islands_desync.geneticAlgorithm.algorithm.genetic_island_algorithm import (
    GeneticIslandAlgorithm,
)
from islands_desync.geneticAlgorithm.generator.island_solution_generator import (
    IslandSolutionGenerator,
)
from islands_desync.geneticAlgorithm.run_hpc.directory_preparation import DirectoryPreparation
from islands_desync.geneticAlgorithm.run_hpc.run_algorithm_params import (
    RunAlgorithmParams,
)
from islands_desync.geneticAlgorithm.utils import datetimer, myDefCrossover
from islands_desync.geneticAlgorithm.utils.myDefMutation import MyUniformMutation
from .benchmark_configuration import create_problem, load_configuration, operator_metadata


def create_algorithm_hpc(
        n, migration, params: RunAlgorithmParams
) -> GeneticIslandAlgorithm:
    configuration = load_configuration()
    NUMBER_OF_VARIABLES = configuration["number_of_variables"]
    NUMBER_OF_EVALUATIONS = configuration["number_of_evaluations"]
    POPULATION_SIZE = configuration["population_size"]
    OFFSPRING_POPULATION_SIZE = configuration["offspring_population_size"]
    problem = create_problem(configuration["problem"], NUMBER_OF_VARIABLES)
    if isinstance(problem, BinaryProblem):
        mutation = BitFlipMutation(1.0 / problem.number_of_bits)
        crossover = SPXCrossover(1.0)
    else:
        mutation = MyUniformMutation(1.0 / problem.number_of_variables, 10.0)
        crossover = myDefCrossover.SwitchCrossover()
    # Opt-in seed: existing launches without ISLANDS_SEED keep their RNG policy.
    if "ISLANDS_SEED" in os.environ:
        seed = int(os.environ["ISLANDS_SEED"]) + n
        random.seed(seed)
        np.random.seed(seed % 2**32)

    # if n==0:
    #     print ("W run_algorithm "+str(sys.argv[1])+"/"+str(sys.argv[4])+" WYSPA,  seria: "+ str(sys.argv[5])+",  interwał: "+str(sys.argv[7])+", liczba migrantów: "+str(sys.argv[6])+" - "+str(sys.argv[2])+" "+str(sys.argv[3]))
    #     print("W pliku json: "+str(configuration["number_of_islands"]))

    genetic_island_algorithm = GeneticIslandAlgorithm(
        problem=problem,
        population_size=POPULATION_SIZE,
        offspring_population_size=OFFSPRING_POPULATION_SIZE,
        ###
        # przy binary solution
        # mutation=BitFlipMutation(0.01),
        # crossover=SPXCrossover(1.0),
        mutation=mutation,
        # 0.5, 9.0),
        # 1.0 / (problem.number_of_variables), 0.2),
        # mutation=PolynomialMutation(
        #    1.0 / 2 * problem.number_of_variables, -20.0),
        crossover=crossover,
        # crossover=SBXCrossover(0.9, 2.0), #9,20
        selection=BinaryTournamentSelection(),
        # selection=RouletteWheelSelection(),
        # nie zbiega sie za szybko
        # mutation=PolynomialMutation(
        #    1.0 / 2 * problem.number_of_variables, 2.0),
        # crossover=SBXCrossover(0.9, 2.0), #9,20
        # selection=BinaryTournamentSelection(),
        # oryginał
        # mutation=PolynomialMutation(
        #    1.0 / problem.number_of_variables, 20.0),
        # crossover=SBXCrossover(0.9, 20.0),
        # selection=BinaryTournamentSelection(),
        ###
        migration_interval=params.migration_interval,  # configuration["migration_interval"],
        number_of_islands= params.island_count,
        number_of_emigrants=params.number_of_emigrants,  # configuration["number_of_migrants"],
        island=n,
        want_create_boxplot=configuration["want_create_boxplot"],
        want_create_plot=configuration["want_create_plot"],
        want_save_migrants_in_txt=configuration["want_save_migrants_in_txt"],
        want_save_diversity_when_improvement=configuration[
            "want_save_diversity_when_improvement"
        ],
        want_tsne_to2=configuration["want_tsne_to2"],
        want_tsne_to3=configuration["want_tsne_to3"],
        want_diversity_to_console=configuration["want_diversity_to_console"],
        want_run_end_communications=configuration["want_run_end_communications"],
        type_of_connection=configuration["type_of_connection"],


        migrant_selection_type=params.strategy,
        migrant_acceptation_strategy=params.strategy2,
        #migrant_selection_type=configuration["migrant_selection_type"],


        how_many_data_intervals=configuration["how_many_data_intervals"],
        plot_population_interval=configuration["plot_population_interval"],
        par_date=params.dda,
        par_time=params.tta,
        wyspWRun=params.island_count,
        seria=params.series_number,
        migration=migration,


        topology=params.topology,


        termination_criterion=StoppingByEvaluations(
            max_evaluations=NUMBER_OF_EVALUATIONS
        ),
        population_generator=IslandSolutionGenerator(island_number=n)
    )

    genetic_island_algorithm.active_operators = operator_metadata(genetic_island_algorithm)
    if n == 0 and hasattr(problem, "benchmark_metadata"):
        metadata = problem.benchmark_metadata()
        metadata["active_operators"] = genetic_island_algorithm.active_operators
        with open(os.path.join(genetic_island_algorithm.path, "benchmark_manifest.json"), "w", encoding="utf-8") as file:
            json.dump(metadata, file, indent=2, allow_nan=False)
    return genetic_island_algorithm
