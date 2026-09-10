"""Thin adapters for the pinned jMetalPy 1.5.5 API; no algorithm changes."""
import random

from jmetal.core.problem import BinaryProblem, FloatProblem
from jmetal.core.solution import BinarySolution


class _MetadataMixin:
    def get_name(self):
        return self._name

    def benchmark_metadata(self):
        from . import SUITE_VERSION
        from .provenance import implementation_sha256
        result = self.evaluator.metadata()
        result.update({"name": self._name, "suite": "benchmarks_refined", "suite_version": SUITE_VERSION,
                       "log_prefix": self._name[:4], "objective_direction": "minimize",
                       "implementation_sha256": implementation_sha256()})
        return result

    @property
    def optimum_value(self):
        return self.evaluator.optimum_value


class ContinuousBenchmarkProblem(_MetadataMixin, FloatProblem):
    def __init__(self, name, evaluator):
        super().__init__()
        self._name, self.evaluator = name, evaluator
        self.number_of_variables = evaluator.dimension
        self.number_of_objectives = 1
        self.number_of_constraints = 0
        self.directions = self.obj_directions = [self.MINIMIZE]
        self.labels = self.obj_labels = ["f(x)"]
        self.lower_bound = [-100.0] * self.number_of_variables
        self.upper_bound = [100.0] * self.number_of_variables

    def evaluate(self, solution):
        solution.objectives[0] = self.evaluator(solution.variables)
        return solution


class BinaryBenchmarkProblem(_MetadataMixin, BinaryProblem):
    def __init__(self, name, evaluator):
        super().__init__()
        self._name, self.evaluator = name, evaluator
        self.number_of_bits = evaluator.dimension
        self.number_of_variables = 1
        self.number_of_objectives = 1
        self.number_of_constraints = 0
        self.number_of_bits_per_variable = [self.number_of_bits]
        self.directions = self.obj_directions = [self.MINIMIZE]
        self.labels = self.obj_labels = ["f(x)"]

    def create_solution(self):
        solution = BinarySolution(1, 1)
        solution.variables[0] = [bool(random.getrandbits(1)) for _ in range(self.number_of_bits)]
        return solution

    def evaluate(self, solution):
        if len(solution.variables) != 1:
            raise ValueError("Binary jMetal solution must have one bit-vector variable")
        solution.objectives[0] = self.evaluator(solution.variables[0])
        return solution
