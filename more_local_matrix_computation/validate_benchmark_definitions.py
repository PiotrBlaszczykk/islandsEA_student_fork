#!/usr/bin/env python3
import math
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(REPO_ROOT / "islands_desync"))

from islands_desync.geneticAlgorithm.utils import benchmark_catalog as catalog  # noqa: E402

try:
    from islands_desync.geneticAlgorithm.utils import benchmark_problems as bp  # noqa: E402
except ModuleNotFoundError as exc:
    if exc.name != "jmetal":
        raise
    bp = None


class BenchmarkDefinitionTests(unittest.TestCase):
    def test_scheduled_suite_shape(self):
        self.assertEqual(30, len(catalog.CONTINUOUS_40_BENCHMARKS))
        self.assertEqual(10, len(catalog.DISCRETE_40_BENCHMARKS))
        self.assertEqual(40, len(catalog.SCHEDULED_40_BENCHMARKS))

    def test_log_prefixes_are_unique(self):
        prefixes = [name[:4] for name in catalog.SCHEDULED_40_BENCHMARKS]
        self.assertEqual(len(prefixes), len(set(prefixes)))

    @unittest.skipIf(bp is None, "jmetal is not installed in this Python environment")
    def test_all_scheduled_problems_instantiate_and_evaluate(self):
        for name in bp.CONTINUOUS_40_BENCHMARKS:
            with self.subTest(name=name):
                problem = bp.create_problem(name, 30)
                solution = problem.create_solution()
                problem.evaluate(solution)
                self.assertTrue(math.isfinite(solution.objectives[0]))

        for name in bp.DISCRETE_40_BENCHMARKS:
            with self.subTest(name=name):
                problem = bp.create_problem(name, 60)
                solution = problem.create_solution()
                problem.evaluate(solution)
                self.assertTrue(math.isfinite(solution.objectives[0]))

    @unittest.skipIf(bp is None, "jmetal is not installed in this Python environment")
    def test_cec_shifted_optima_for_simple_functions(self):
        # These CEC2014 functions have transformations whose generated shift
        # point evaluates to the documented bias in this implementation.
        for fid in range(1, 13):
            name = bp.CONTINUOUS_40_BENCHMARKS[fid - 1]
            problem = bp.create_problem(name, 30)
            solution = problem.create_solution()
            solution.variables = bp._cec_shift(fid, 30).tolist()
            problem.evaluate(solution)
            self.assertAlmostEqual(100.0 * fid, solution.objectives[0], places=3)

    @unittest.skipIf(bp is None, "jmetal is not installed in this Python environment")
    def test_selected_binary_known_values(self):
        checks = {
            "d04_onemax": ([True] * 60, -60.0),
            "d05_zeromax": ([False] * 60, -60.0),
            "d06_leading_ones": ([True] * 60, -60.0),
            "d07_alternating_bits": ([index % 2 == 0 for index in range(60)], -60.0),
            "d08_trap4": ([True] * 60, -60.0),
            "d09_royal_road4": ([True] * 60, -60.0),
            "d10_maxcut_ring": ([index % 2 == 0 for index in range(60)], -60.0),
        }
        for name, (bits, expected) in checks.items():
            with self.subTest(name=name):
                problem = bp.create_problem(name, 60)
                solution = problem.create_solution()
                solution.variables[0] = bits
                problem.evaluate(solution)
                self.assertEqual(expected, solution.objectives[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
