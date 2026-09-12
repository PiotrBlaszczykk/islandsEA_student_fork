from itertools import product
import json
import math
import random
import unittest

import numpy as np

from islands_desync.geneticAlgorithm.utils.benchmarks_refined.discrete import BinaryBenchmark, DISCRETE_BENCHMARKS


def scalar_reference(index, bits):
    """Independent scalar definitions with the legacy objective convention."""
    n = len(bits)
    if index == 1:
        correlations = [sum((1 if bits[i] else -1) * (1 if bits[i+k] else -1)
                            for i in range(n-k)) for k in range(1, n)]
        return -n*n / (2 * sum(c*c for c in correlations))
    if index in (2, 8):
        size = 5 if index == 2 else 4
        score = 0
        for start in range(0, n, size):
            ones = sum(bits[start:start+size])
            score += size if ones == size else size-1-ones
        return -score
    if index == 3:
        rng = random.Random(20260511)
        tables = [[rng.random() for _ in range(32)] for _ in range(n)]
        return -sum(tables[i][sum(int(bits[(i+j) % n]) * 2**(4-j) for j in range(5))]
                    for i in range(n)) / n
    if index == 4:
        return -sum(bits)
    if index == 5:
        return -sum(1-b for b in bits)
    if index == 6:
        return -next((i for i, b in enumerate(bits) if not b), n)
    if index == 7:
        matches = sum(b == (i % 2 == 0) for i, b in enumerate(bits))
        return -max(matches, n-matches)
    if index == 9:
        return -sum(4 for i in range(0, n, 4) if all(bits[i:i+4]))
    return -sum(bits[i] != bits[(i+1) % n] for i in range(n))


class DiscreteTests(unittest.TestCase):
    def test_exhaustive_small_instances(self):
        for index, name in enumerate(DISCRETE_BENCHMARKS, 1):
            n = 10 if index == 2 else 8
            evaluator = BinaryBenchmark(name, n)
            best = float("inf")
            for bits in product((0, 1), repeat=n):
                actual = evaluator(bits)
                self.assertAlmostEqual(scalar_reference(index, bits), actual, places=14, msg=str((name, bits)))
                best = min(best, actual)
            if evaluator.optimum_value is not None:
                self.assertEqual(evaluator.optimum_value, best, name)
                self.assertEqual(best, evaluator(evaluator.optimum_position))

    def test_all_at_production_bit_counts(self):
        rng = random.Random(731)
        for n in (60, 100, 200):
            for index, name in enumerate(DISCRETE_BENCHMARKS, 1):
                evaluator = BinaryBenchmark(name, n)
                for _ in range(5):
                    bits = [rng.randrange(2) for _ in range(n)]
                    self.assertAlmostEqual(scalar_reference(index, bits), evaluator(bits), places=14)
                if evaluator.optimum_position is not None:
                    self.assertEqual(evaluator.optimum_value, evaluator(evaluator.optimum_position))

    def test_lab_merit_sign_and_parity_of_maxcut(self):
        labs = BinaryBenchmark("b01_labs_binary", 2)
        self.assertEqual(-2., labs([0, 1]))
        for n in (3, 5, 7, 10):
            cut = BinaryBenchmark("b10_maxcut_ring", n)
            self.assertEqual(-(n-n % 2), cut(cut.optimum_position))
        self.assertIsNone(labs.optimum_value)
        self.assertIsNone(BinaryBenchmark("b03_nk_k4", 60).optimum_value)

    def test_validation(self):
        for name in DISCRETE_BENCHMARKS:
            for invalid in (0, -1, True, 60.0):
                with self.assertRaises(ValueError):
                    BinaryBenchmark(name, invalid)
            evaluator = BinaryBenchmark(name, 60)
            for invalid in ([2] * 60, [-1] * 60, [float("nan")] * 60, ["0"] * 60,
                            [0j] * 60, [0] * 59, [[0] * 60]):
                with self.assertRaises(ValueError):
                    evaluator(invalid)
        for name, n in (("b01_labs_binary", 1), ("b02_trap5", 11), ("b03_nk_k4", 4),
                        ("b08_trap4", 10), ("b09_royal_road4", 10), ("b10_maxcut_ring", 2)):
            with self.assertRaises(ValueError):
                BinaryBenchmark(name, n)

    def test_determinism_and_metadata(self):
        state = random.getstate()
        evaluate = BinaryBenchmark("b03_nk_k4", 60)
        bits = [0, 1] * 30
        expected = evaluate(bits)
        self.assertEqual(state, random.getstate())
        self.assertEqual(expected, BinaryBenchmark("b03_nk_k4", 60)(bits))
        self.assertNotEqual(expected, BinaryBenchmark("b03_nk_k4", 60, 7)(bits))
        self.assertEqual(bits, [0, 1] * 30)
        metadata = evaluate.metadata()
        self.assertEqual(metadata, json.loads(json.dumps(metadata, allow_nan=False)))
        metadata["instance"]["tables"][0][0] = -100
        self.assertEqual(expected, evaluate(bits))
        self.assertNotEqual(metadata, evaluate.metadata())
