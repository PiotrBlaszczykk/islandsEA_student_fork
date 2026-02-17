import json
from datetime import datetime, timedelta

from jmetal.operator import BinaryTournamentSelection
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


def create_algorithm_hpc(
        n, migration, params: RunAlgorithmParams
) -> GeneticIslandAlgorithm:
    conf_file = "./islands_desync/geneticAlgorithm/algorithm/configurations/algorithm_configuration.json"

    with open(conf_file) as file:
        configuration = json.loads(file.read())

    try:
        NUMBER_OF_VARIABLES = int(configuration["number_of_variables"])
        NUMBER_OF_EVALUATIONS = int(configuration["number_of_evaluations"])
        POPULATION_SIZE = int(configuration["population_size"])
        OFFSPRING_POPULATION_SIZE = int(configuration["offspring_population_size"])

        if NUMBER_OF_VARIABLES <= 0:
            raise ValueError("Number of variables have to be positive")
        if NUMBER_OF_EVALUATIONS <= 0:
            raise ValueError("Number of evaluations have to be positive")
        if POPULATION_SIZE <= 0:
            raise ValueError("Population size has to be positive")
        if OFFSPRING_POPULATION_SIZE <= 0:
            raise ValueError("Offspring population size have to be positive")
    except ValueError:
        print("Invalid configuration")

    #
    #problem = Rastrigin(NUMBER_OF_VARIABLES)
    #
    problem = Sphere(NUMBER_OF_VARIABLES)

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
        mutation=MyUniformMutation(1 / (problem.number_of_variables), 10.0), #number_of_variables()
        # 0.5, 9.0),
        # 1.0 / (problem.number_of_variables), 0.2),
        # mutation=PolynomialMutation(
        #    1.0 / 2 * problem.number_of_variables, -20.0),
        crossover=myDefCrossover.SwitchCrossover(),
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
