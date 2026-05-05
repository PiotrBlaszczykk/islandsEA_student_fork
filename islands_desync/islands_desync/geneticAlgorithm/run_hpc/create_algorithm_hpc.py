import json
import os
from datetime import datetime, timedelta

from jmetal.core.problem import BinaryProblem
from jmetal.operator import BinaryTournamentSelection
from jmetal.operator import BitFlipMutation
from jmetal.operator import SPXCrossover
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
from islands_desync.geneticAlgorithm.utils import myDefProblems
from islands_desync.geneticAlgorithm.utils.myDefMutation import MyUniformMutation


def _env_or_config(configuration, env_name, config_name):
    return os.environ.get(env_name, configuration[config_name])


def _create_problem(problem_name: str, number_of_variables: int):
    normalized = problem_name.strip().lower()

    if normalized in ("sphere", "sphe"):
        return Sphere(number_of_variables)
    if normalized in ("rastrigin", "rast"):
        return Rastrigin(number_of_variables)
    if normalized in ("ackley", "ackl"):
        return myDefProblems.Ackley(number_of_variables)
    if normalized in ("schwefel", "rotated", "rotated_hyper_ellipsoid", "roth"):
        return myDefProblems.Schwefel(number_of_variables)
    if normalized in ("labs", "labs_float", "labs_sign"):
        return myDefProblems.Labs(number_of_variables)
    if normalized in ("labs_binary", "binary_labs", "labb"):
        return myDefProblems.LabsBinary(number_of_variables)

    raise ValueError(
        "Unknown ISLANDS_PROBLEM='{}'. Use one of: sphere, rastrigin, "
        "ackley, schwefel, labs, labs_binary.".format(problem_name)
    )


def create_algorithm_hpc(
        n, migration, params: RunAlgorithmParams
) -> GeneticIslandAlgorithm:
    conf_file = "./islands_desync/geneticAlgorithm/algorithm/configurations/algorithm_configuration.json"

    with open(conf_file) as file:
        configuration = json.loads(file.read())

    try:
        NUMBER_OF_VARIABLES = int(
            _env_or_config(
                configuration, "ISLANDS_NUMBER_OF_VARIABLES", "number_of_variables"
            )
        )
        NUMBER_OF_EVALUATIONS = int(
            _env_or_config(
                configuration, "ISLANDS_NUMBER_OF_EVALUATIONS", "number_of_evaluations"
            )
        )
        POPULATION_SIZE = int(
            _env_or_config(configuration, "ISLANDS_POPULATION_SIZE", "population_size")
        )
        OFFSPRING_POPULATION_SIZE = int(
            _env_or_config(
                configuration,
                "ISLANDS_OFFSPRING_POPULATION_SIZE",
                "offspring_population_size",
            )
        )

        if NUMBER_OF_VARIABLES <= 0:
            raise ValueError("Number of variables have to be positive")
        if NUMBER_OF_EVALUATIONS <= 0:
            raise ValueError("Number of evaluations have to be positive")
        if POPULATION_SIZE <= 0:
            raise ValueError("Population size has to be positive")
        if OFFSPRING_POPULATION_SIZE <= 0:
            raise ValueError("Offspring population size have to be positive")
    except ValueError as exc:
        raise ValueError("Invalid algorithm configuration") from exc

    problem_name = os.environ.get("ISLANDS_PROBLEM", configuration.get("problem", "sphere"))
    problem = _create_problem(problem_name, NUMBER_OF_VARIABLES)

    if isinstance(problem, BinaryProblem):
        mutation = BitFlipMutation(1.0 / NUMBER_OF_VARIABLES)
        crossover = SPXCrossover(1.0)
    else:
        mutation = MyUniformMutation(1 / (problem.number_of_variables), 10.0)
        crossover = myDefCrossover.SwitchCrossover()

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

    return genetic_island_algorithm
