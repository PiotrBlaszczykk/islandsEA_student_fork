"""Numeric coordinates for logging/distance; jMetal stores bits in nested lists."""
from jmetal.core.solution import BinarySolution


def decision_variables(solution):
    if isinstance(solution, BinarySolution):
        return [int(bit) for variable in solution.variables for bit in variable]
    return solution.variables
