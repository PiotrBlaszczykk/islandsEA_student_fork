from typing import List

from jmetal.core.solution import BinarySolution


class BinaryIslandSolution(BinarySolution):
    def __init__(
        self,
        number_of_variables: int,
        number_of_objectives: int,
        number_of_constants: int,
        variables,
        objectives,
        constraints,
        from_island: int,
        from_evaluation: int,
    ):
        super(BinaryIslandSolution, self).__init__(
            number_of_variables, number_of_objectives, number_of_constants
        )
        self.from_island = from_island
        self.from_evaluation = from_evaluation
        self.variables = variables
        self.objectives = objectives
        self.constraints = constraints

    def __str__(self) -> str:
        return "Binary Island Solution(variables={},objectives={},constraints={},from_island={},from_evaluation={})".format(
            self.variables,
            self.objectives,
            self.constraints,
            self.from_island,
            self.from_evaluation,
        )

    def pprint_fitness(self):
        print(str(self.objectives))

    def pprint_from_and_fitness(self):
        print(str(self.from_island) + " " + str(self.objectives))

    def get_fitness(self):
        return self.objectives[0]

    def get_from_and_fitness(self):
        return str(self.from_island) + " " + str(self.objectives)

    def copy(self):
        new_solution = BinaryIslandSolution(
            self.number_of_variables,
            self.number_of_objectives,
            self.number_of_constraints,
            self.variables[:],
            self.objectives[:],
            self.constraints[:],
            self.from_island,
            self.from_evaluation,
        )

        return new_solution
