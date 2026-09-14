import itertools
import os
import random
import unittest

import numpy as np

from islands_desync.geneticAlgorithm.utils.benchmarks_refined import BENCHMARKS, create_evaluator
from islands_desync.geneticAlgorithm.utils.benchmarks_refined.batch import NumpyBatchBackend
from islands_desync.geneticAlgorithm.utils.benchmarks_refined.batch_validation import validate_backend, tolerances


class BatchTests(unittest.TestCase):
    def test_numpy_all_functions_dimensions_and_golden(self):
        report = validate_backend(NumpyBatchBackend())
        self.assertEqual(40, report["benchmark_count"])
        self.assertEqual(170, report["instance_count"])

    def test_validation_and_empty_batches(self):
        backend = NumpyBatchBackend(max_batch_size=4)
        for name, dimension in (("r01_elliptic", 10), ("b04_onemax", 20)):
            empty = backend.evaluate_batch(name, np.empty((0, dimension)))
            self.assertEqual((0,), empty.shape)
            for invalid in (np.zeros(dimension), np.zeros((5, dimension)), np.full((1, dimension), np.nan),
                            np.full((1, dimension), 1j), np.full((1, dimension), "1"), np.full((1, dimension), 101)):
                with self.subTest(name=name, input=str(invalid)[:30]), self.assertRaises(ValueError):
                    backend.evaluate_batch(name, invalid)
        with self.assertRaises(ValueError):
            backend.evaluate_batch("r01_elliptic", np.ones((1, 10), dtype=bool))
        for dimension in (10.0, True, 20):
            with self.assertRaises(ValueError):
                backend.prepare("r01_elliptic", dimension)
        for seed in (True, -1, 1.0):
            with self.assertRaises(ValueError):
                backend.prepare("b03_nk_k4", 20, instance_seed=seed)
        with self.assertRaises(KeyError):
            backend.evaluate_batch("not-a-problem", np.zeros((1, 10)))
        with self.assertRaises(ValueError):
            backend.evaluate_batch("b02_trap5", np.zeros((1, 12)))

    def test_binary_exhaustive_small_dimensions_and_rng(self):
        backend = NumpyBatchBackend()
        for name in BENCHMARKS[30:]:
            dimension = 5 if name in ("b02_trap5", "b03_nk_k4") else 4
            x = np.array(list(itertools.product((0, 1), repeat=dimension)))
            scalar = create_evaluator(name, dimension)
            state = random.getstate()
            for dtype in (bool, np.uint8, np.int64, np.float64):
                actual = backend.evaluate_batch(name, x.astype(dtype))
                rtol, atol = tolerances(name)
                np.testing.assert_allclose(actual, [scalar(row) for row in x], rtol=rtol, atol=atol)
            self.assertEqual(state, random.getstate())

    def test_cached_data_and_nk_seed_are_isolated(self):
        backend = NumpyBatchBackend()
        key = backend.prepare("r29_composition7", 200)
        instance = backend._instances[key]
        backend.evaluate_batch("r29_composition7", np.zeros((2, 200)))
        self.assertIs(instance, backend._instances[key])
        x = np.zeros((4, 20))
        baseline = backend.evaluate_batch("b03_nk_k4", x)
        changed = backend.evaluate_batch("b03_nk_k4", x, instance_seed=123)
        self.assertFalse(np.array_equal(baseline, changed))
        np.testing.assert_array_equal(baseline, backend.evaluate_batch("b03_nk_k4", x))

    @unittest.skipUnless(os.environ.get("ISLANDS_TEST_CUPY") == "1", "Real GPU validation requires explicit ISLANDS_TEST_CUPY=1")
    def test_real_cupy_all_functions(self):
        # Import/device failures must FAIL when GPU validation is requested.
        from islands_desync.geneticAlgorithm.utils.benchmarks_refined.batch import CupyBatchBackend
        backend = CupyBatchBackend()
        report = validate_backend(backend)
        self.assertEqual(40, report["benchmark_count"])
        self.assertEqual(170, report["instance_count"])


if __name__ == "__main__":
    unittest.main()
