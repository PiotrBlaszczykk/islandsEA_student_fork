import json
import sys
from math import trunc

import pika as pika
from algorithm.genetic_island_algorithm import GeneticIslandAlgorithm
from generator.island_solution_generator import IslandSolutionGenerator
from jmetal.operator import (
    BinaryTournament2Selection,
    BinaryTournamentSelection,
    BitFlipMutation,
    PolynomialMutation,
    SBXCrossover,
    SPXCrossover,
    UniformMutation,
)
from jmetal.operator.selection import RouletteWheelSelection
from jmetal.problem.singleobjective.unconstrained import Rastrigin, Sphere
from jmetal.util.termination_criterion import StoppingByEvaluations

from islands_desync.geneticAlgorithm.migrations.queue_migration import QueueMigration
from islands_desync.geneticAlgorithm.utils import (
    datetimer,
    myDefCrossover,
    myDefMutation,
    myDefProblems,
)
from islands_desync.geneticAlgorithm.utils.create_rabbitmq_channels import (
    CreateRabbitmqChannels,
)
from islands_desync.geneticAlgorithm.utils.myDefMutation import MyUniformMutation


def run():
    czasStart = dta.teraz()

    conf_file = "algorithm/configurations/algorithm_configuration.json"
    island = int(sys.argv[1])
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

    # problem = myDefProblems.Labs(NUMBER_OF_VARIABLES)
    # problem = myDefProblems.Schwefel(NUMBER_OF_VARIABLES)
    # problem = myDefProblems.Ackley(NUMBER_OF_VARIABLES)
    # problem = Sphere(NUMBER_OF_VARIABLES)
    # 
    problem = Rastrigin(NUMBER_OF_VARIABLES)

    rabbitmq_delays = configuration["island_delays"]

    channel = CreateRabbitmqChannels(
        configuration["number_of_islands"],
        island,
        data_interval=round(
            NUMBER_OF_EVALUATIONS // configuration["how_many_data_intervals"]
        ),
        last_step=trunc(
            (NUMBER_OF_EVALUATIONS - POPULATION_SIZE) / OFFSPRING_POPULATION_SIZE
        ),
        max_evaluations=NUMBER_OF_EVALUATIONS,
        rabbitmq_delays=rabbitmq_delays,
        population_size=POPULATION_SIZE,
        offspring_population_size=OFFSPRING_POPULATION_SIZE,
        wyspWRun=int(sys.argv[4]),
    ).create_channels()
    migration = QueueMigration(
        island,
        channel=channel,
        number_of_islands=configuration["number_of_islands"],
        rabbitmq_delays=rabbitmq_delays,
    )

    if island == 0:
        print(
            "W run_algorithm "
            + str(sys.argv[1])
            + "/"
            + str(sys.argv[4])
            + " WYSPA,  seria: "
            + str(sys.argv[5])
            + ",  interwał: "
            + str(sys.argv[7])
            + ", liczba migrantów: "
            + str(sys.argv[6])
            + " - "
            + str(sys.argv[2])
            + " "
            + str(sys.argv[3])
        )
        print("W pliku json: " + str(configuration["number_of_islands"]))

    genetic_island_algorithm = GeneticIslandAlgorithm(
        problem=problem,
        population_size=POPULATION_SIZE,
        offspring_population_size=OFFSPRING_POPULATION_SIZE,
        ###
        # przy binary solution
        # mutation=BitFlipMutation(0.01),
        # crossover=SPXCrossover(1.0),
        mutation=MyUniformMutation(1 / (problem.number_of_variables()), 10.0),
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
        migration_interval=int(sys.argv[7]),  # configuration["migration_interval"],
        number_of_islands=configuration["number_of_islands"],
        number_of_emigrants=int(sys.argv[6]),  # configuration["number_of_migrants"],
        island=island,
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
        migrant_selection_type=configuration["migrant_selection_type"],
        how_many_data_intervals=configuration["how_many_data_intervals"],
        plot_population_interval=configuration["plot_population_interval"],
        par_date=str(sys.argv[2]),
        par_time=str(sys.argv[3]),
        wyspWRun=int(sys.argv[4]),
        seria=int(sys.argv[5]),
        termination_criterion=StoppingByEvaluations(
            max_evaluations=NUMBER_OF_EVALUATIONS
        ),
        population_generator=IslandSolutionGenerator(island_number=island),
    )

    # oryginał
    """mutation=PolynomialMutation(
        1.0 / problem.number_of_variables, 20.0),
    crossover=SBXCrossover(0.9, 20.0),
    selection=BinaryTournamentSelection(),"""

    genetic_island_algorithm.run()
    result = genetic_island_algorithm.get_result()
    """    print(f'Solution: {result}') """
    print(f"\nIsland: {island} Fitness: {result.objectives[0]}")
    print("czas trwania: " + str(dta.teraz() - czasStart))


def __str__(self):
    return "run_algorithm"


def __del__(self):
    print("koniec run_algorithm")


if __name__ == "__main__":
    dta = datetimer.Datetimer("run_algorithm", False)
    run()
