"""Refined versions of the existing 30 CEC2014 + 10 binary benchmarks.

Use ``create_evaluator(name, dimension)`` without jMetal, or ``create_problem``
for the project's jMetalPy 1.5.5 runtime. New rNN_/bNN_ prefixes keep corrected
CEC instances distinguishable from historical cNN_/dNN_ outputs.
"""
from .discrete import BinaryBenchmark, DEFAULT_INSTANCE_SEED, DISCRETE_BENCHMARKS

SUITE_VERSION = "1.0.0"
_CEC_SUFFIXES = (
    "elliptic", "bent_cigar", "discus", "rosenbrock", "ackley", "weierstrass",
    "griewank", "rastrigin", "rot_rastrigin", "schwefel", "rot_schwefel", "katsuura",
    "happycat", "hgbat", "grie_rosen", "schaffer_f6", "hybrid1", "hybrid2",
    "hybrid3", "hybrid4", "hybrid5", "hybrid6", "composition1", "composition2",
    "composition3", "composition4", "composition5", "composition6", "composition7", "composition8",
)
CONTINUOUS_BENCHMARKS = tuple(f"r{i:02d}_{suffix}" for i, suffix in enumerate(_CEC_SUFFIXES, 1))
BENCHMARKS = CONTINUOUS_BENCHMARKS + DISCRETE_BENCHMARKS


def is_registered_problem(name):
    return str(name).strip().lower() in BENCHMARKS


def create_evaluator(name, dimension=None, *, instance_seed=DEFAULT_INSTANCE_SEED):
    key = str(name).strip().lower()
    if key in CONTINUOUS_BENCHMARKS:
        if instance_seed != DEFAULT_INSTANCE_SEED:
            raise ValueError("CEC2014 uses fixed official data, not a configurable random seed")
        from .cec2014 import CEC2014
        return CEC2014(CONTINUOUS_BENCHMARKS.index(key) + 1, 30 if dimension is None else dimension)
    if key in DISCRETE_BENCHMARKS:
        return BinaryBenchmark(key, 60 if dimension is None else dimension, instance_seed)
    raise KeyError(f"Unknown refined benchmark: {name!r}; use one of BENCHMARKS")


def create_problem(problem_name, number_of_variables=None, *, instance_seed=DEFAULT_INSTANCE_SEED):
    from .adapters import BinaryBenchmarkProblem, ContinuousBenchmarkProblem
    key = str(problem_name).strip().lower()
    evaluator = create_evaluator(key, number_of_variables, instance_seed=instance_seed)
    adapter = ContinuousBenchmarkProblem if key in CONTINUOUS_BENCHMARKS else BinaryBenchmarkProblem
    return adapter(key, evaluator)


__all__ = ["BENCHMARKS", "CONTINUOUS_BENCHMARKS", "DISCRETE_BENCHMARKS", "SUITE_VERSION",
           "create_evaluator", "create_problem", "is_registered_problem"]
