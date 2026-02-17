import random

from jmetal.core.operator import Mutation
from jmetal.core.solution import FloatSolution
from jmetal.util.ckecking import Check


class MyUniformMutation(Mutation[FloatSolution]):
    def __init__(self, probability: float, perturbation: float = 0.5):
        super(MyUniformMutation, self).__init__(probability=probability)
        self.perturbation = perturbation

    def execute(self, solution: FloatSolution) -> FloatSolution:
        Check.that(issubclass(type(solution), FloatSolution), "Solution type invalid")

        for i in range(solution.number_of_variables):
            rand = random.random()

            if rand <= self.probability:
                tmp = (random.random() - 0.5) * self.perturbation
                tmp += solution.variables[i]

                if tmp < solution.lower_bound[i]:
                    tmp = solution.lower_bound[i]
                elif tmp > solution.upper_bound[i]:
                    tmp = solution.upper_bound[i]

                solution.variables[i] = tmp

        return solution

    def get_name(self):
        return "My Uniform mutation"


class MyNonUniformMutation(Mutation[FloatSolution]):
    def __init__(
        self, probability: float, perturbation: float = 0.5, max_iterations: int = 0.5
    ):
        super(MyNonUniformMutation, self).__init__(probability=probability)
        self.perturbation = perturbation
        self.max_iterations = max_iterations
        self.current_iteration = 0

    def execute(self, solution: FloatSolution) -> FloatSolution:
        Check.that(type(solution) is FloatSolution, "Solution type invalid")

        for i in range(solution.number_of_variables):
            if random.random() <= self.probability:
                rand = random.random()

                if rand <= 0.5:
                    tmp = self.__delta(
                        solution.upper_bound[i] - solution.variables[i],
                        self.perturbation,
                    )
                else:
                    tmp = self.__delta(
                        solution.lower_bound[i] - solution.variables[i],
                        self.perturbation,
                    )

                tmp += solution.variables[i]

                if tmp < solution.lower_bound[i]:
                    tmp = solution.lower_bound[i]
                elif tmp > solution.upper_bound[i]:
                    tmp = solution.upper_bound[i]

                solution.variables[i] = tmp

        return solution

    def set_current_iteration(self, current_iteration: int):
        self.current_iteration = current_iteration

    def __delta(self, y: float, b_mutation_parameter: float):
        return y * (
            1.0
            - pow(
                random.random(),
                pow(
                    (1.0 - 1.0 * self.current_iteration / self.max_iterations),
                    b_mutation_parameter,
                ),
            )
        )

    def get_name(self):
        return "My Non Uniform mutation"
