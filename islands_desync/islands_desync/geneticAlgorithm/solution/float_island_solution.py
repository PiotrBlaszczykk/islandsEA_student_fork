from typing import List

from jmetal.core.solution import FloatSolution


class FloatIslandSolution(FloatSolution):
    def __init__(
        self,
        lower_bound: List[float],
        upper_bound: List[float],
        number_of_objectives: int,
        number_of_constants: int,
        variables,
        objectives,
        constraints,
        from_island: int,
        from_evaluation: int,
    ):
        super(FloatIslandSolution, self).__init__(
            lower_bound, upper_bound, number_of_objectives, number_of_constants
        )
        self.from_island = from_island
        self.from_evaluation = from_evaluation
        self.variables = variables
        self.objectives = objectives
        self.constraints = constraints

    def __str__(self) -> str:
        return "Float Island Solution(variables={},objectives={},constraints={},from_island={},from_evaluation={})".format(
            self.variables,
            self.objectives,
            self.constraints,
            self.from_island,
            self.from_evaluation,
        )

    def __del__(self):
        pass
        # print("============ DEL ============")

    def pprint_fitness(self):
        print(str(self.objectives))

    def pprint_from_and_fitness(self):
        print(str(self.from_island) + " " + str(self.objectives))

    def get_fitness(self):
        return self.objectives[0]

    def get_from_and_fitness(self):
        return str(self.from_island) + " " + str(self.objectives)

    def copy(self):
        new_solution = FloatIslandSolution(
            self.lower_bound,
            self.upper_bound,
            self.number_of_objectives,
            self.number_of_constraints,
            self.variables[:],
            self.objectives[:],
            self.constraints[:],
            self.from_island,
            self.from_evaluation,
        )

        return new_solution
