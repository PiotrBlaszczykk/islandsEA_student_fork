import gzip
import json
import math
from pathlib import Path
import random
import unittest

import numpy as np

from islands_desync.geneticAlgorithm.utils.benchmarks_refined.cec2014 import CEC2014, SUPPORTED_DIMENSIONS


class CECReferenceTests(unittest.TestCase):
    def test_official_c_reference(self):
        path = Path(__file__).with_name("reference") / "cec2014_golden.json.gz"
        reference = json.loads(gzip.decompress(path.read_bytes()))
        cases = reference["cases"]
        self.assertEqual(1776, len(cases))
        self.assertEqual({(f, d) for f in range(1, 31) for d in SUPPORTED_DIMENSIONS},
                         {(c["fid"], c["dimension"]) for c in cases})
        evaluators = {}
        for case in cases:
            key = case["fid"], case["dimension"]
            if key not in evaluators:
                evaluators[key] = CEC2014(*key)
            with self.subTest(fid=key[0], dimension=key[1], point=case["point"]):
                actual = evaluators[key](case["x"])
                self.assertTrue(math.isclose(actual, case["expected"], rel_tol=1e-10, abs_tol=1e-8),
                                f"Python={actual!r}, official C={case['expected']!r}")
        self.assertEqual(reference["source_commit"], evaluators[(1, 10)].metadata()["source_commit"])

    def test_all_official_shifted_optima(self):
        for fid in range(1, 31):
            for dim in SUPPORTED_DIMENSIONS:
                with self.subTest(fid=fid, dimension=dim):
                    evaluator = CEC2014(fid, dim)
                    self.assertLessEqual(abs(evaluator(evaluator.optimum_position) - fid * 100), 1e-8)

    def test_domain_validation(self):
        for dim in (0, 1, 2, 20, 200, 30.0, True):
            with self.subTest(dimension=dim), self.assertRaises(ValueError):
                CEC2014(1, dim)
        for fid in (0, 31, True, 1.0):
            with self.assertRaises(ValueError):
                CEC2014(fid, 10)
        evaluate = CEC2014(1, 10)
        for invalid in ([0] * 9, [[0] * 10], [float("nan")] * 10, [float("inf")] * 10,
                        [101] * 10, [-101] * 10, ["0"] * 10, [0j] * 10, [True] * 10):
            with self.subTest(candidate=str(invalid)), self.assertRaises(ValueError):
                evaluate(invalid)

    def test_input_rng_and_instance_independence(self):
        x = np.linspace(-90, 90, 30)
        before = x.copy()
        state = random.getstate()
        first = CEC2014(29, 30)
        expected = first(x)
        CEC2014(2, 10)([0.] * 10)
        CEC2014(30, 30)(x)
        self.assertEqual(expected, first(x))
        self.assertEqual(state, random.getstate())
        np.testing.assert_array_equal(before, x)
        optimum = first.optimum_position
        optimum[:] = 0
        self.assertFalse(np.all(first.optimum_position == 0))
