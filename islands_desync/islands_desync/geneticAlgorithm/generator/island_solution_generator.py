from typing import TypeVar

from jmetal.core.problem import Problem
from jmetal.core.solution import BinarySolution, FloatSolution
from jmetal.util.generator import Generator

from islands_desync.geneticAlgorithm.solution.binary_island_solution import (
    BinaryIslandSolution,
)
from islands_desync.geneticAlgorithm.solution.float_island_solution import (
    FloatIslandSolution,
)

R = TypeVar("R")


class IslandSolutionGenerator(Generator):
    def __init__(self, island_number):
        self.island_number = island_number

    def new(self, problem: Problem):
        solution = problem.create_solution()
        if isinstance(solution, FloatSolution):
            return FloatIslandSolution(
                solution.lower_bound,
                solution.upper_bound,
                solution.number_of_objectives,
                solution.number_of_constraints,
                solution.variables,
                solution.objectives,
                solution.constraints,
                from_island=self.island_number,
                from_evaluation=0,
            )
        else:
            return solution
        """elif isinstance(solution, BinarySolution):
                    return BinaryIslandSolution(solution.number_of_variables, solution.number_of_objectives, solution.number_of_constraints,
                                              solution.variables, solution.objectives, solution.constraints,
                                              from_island=self.island_number, from_evaluation=0)"""
