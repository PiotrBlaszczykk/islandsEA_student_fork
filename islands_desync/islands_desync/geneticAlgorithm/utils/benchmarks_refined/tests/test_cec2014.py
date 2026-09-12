import gzip
import hashlib
import json
import math
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from islands_desync.geneticAlgorithm.utils.benchmarks_refined import cec2014
from islands_desync.geneticAlgorithm.utils.benchmarks_refined.cec2014 import CEC2014, OFFICIAL_DIMENSIONS, SUPPORTED_DIMENSIONS


class CECReferenceTests(unittest.TestCase):
    def test_official_c_reference(self):
        path = Path(__file__).with_name("reference") / "cec2014_golden.json.gz"
        reference = json.loads(gzip.decompress(path.read_bytes()))
        cases = reference["cases"]
        self.assertEqual(1776, len(cases))
        self.assertEqual({(f, d) for f in range(1, 31) for d in OFFICIAL_DIMENSIONS},
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

    def test_d200_c_reference(self):
        path = Path(__file__).with_name("reference") / "cec2014_d200_golden.json.gz"
        reference = json.loads(gzip.decompress(path.read_bytes()))
        self.assertFalse(reference["official_cec2014_instance"])
        self.assertEqual(444, len(reference["cases"]))
        self.assertEqual({(f, 200) for f in range(1, 31)},
                         {(c["fid"], c["dimension"]) for c in reference["cases"]})
        evaluators = {fid: CEC2014(fid, 200) for fid in range(1, 31)}
        for case in reference["cases"]:
            with self.subTest(fid=case["fid"], point=case["point"]):
                actual = evaluators[case["fid"]](case["x"])
                self.assertTrue(math.isclose(actual, case["expected"], rel_tol=1e-10, abs_tol=1e-8),
                                f"Python={actual!r}, C with generated 200D data={case['expected']!r}")
        self.assertEqual(reference["data_sha256"], evaluators[1].metadata()["data_sha256"])

    def test_d200_instance_data_and_provenance(self):
        state = random.getstate()
        for fid in range(1, 31):
            evaluator = CEC2014(fid, 200)
            self.assertEqual((evaluator._shifts.shape[0], 200), evaluator._shifts.shape)
            self.assertTrue(np.all(np.abs(evaluator._shifts) <= 80.0))
            self.assertFalse(evaluator._shifts.flags.writeable)
            self.assertFalse(evaluator._matrices.flags.writeable)
            for matrix in evaluator._matrices:
                # The documented extension has ten randomized 20D blocks,
                # each with singular values ranging from 1 to 2.
                np.testing.assert_array_equal(np.count_nonzero(matrix, axis=1), np.full(200, 20))
                singular = np.linalg.svd(matrix, compute_uv=False)
                self.assertAlmostEqual(1.0, singular[-1], places=12)
                self.assertAlmostEqual(2.0, singular[0], places=12)
            if evaluator._shuffles is not None:
                for shuffle in evaluator._shuffles:
                    np.testing.assert_array_equal(np.sort(shuffle), np.arange(200))
            metadata = evaluator.metadata()
            self.assertFalse(metadata["official_cec2014_instance"])
            self.assertEqual("islandsea-cec2014-d200-v1", metadata["instance"])
            self.assertEqual(20260911, metadata["generation"]["seed"])
            metadata["generation"]["seed"] = -1
            self.assertEqual(20260911, evaluator.metadata()["generation"]["seed"])
            x = np.linspace(-90, 90, 200)
            before = x.copy()
            self.assertEqual(evaluator(x), CEC2014(fid, 200)(x))
            np.testing.assert_array_equal(before, x)
        self.assertEqual(state, random.getstate())
        self.assertTrue(CEC2014(1, 100).metadata()["official_cec2014_instance"])

    def test_d200_checksum_rejects_corrupted_data(self):
        with tempfile.TemporaryDirectory(prefix="cec200-checksum-") as directory:
            root = Path(directory)
            extension = root / "d200"
            extension.mkdir()
            (extension / "cec2014.npz").write_bytes(b"corrupted")
            (extension / "manifest.json").write_text(json.dumps({"data_sha256": hashlib.sha256(b"expected").hexdigest()}))
            cec2014._verified_provenance.cache_clear()
            try:
                with patch.object(cec2014, "_DATA_FILE", root / "cec2014.npz"):
                    with self.assertRaisesRegex(RuntimeError, "checksum mismatch"):
                        cec2014._verified_provenance(True)
            finally:
                cec2014._verified_provenance.cache_clear()

    def test_all_shifted_optima(self):
        for fid in range(1, 31):
            for dim in SUPPORTED_DIMENSIONS:
                with self.subTest(fid=fid, dimension=dim):
                    evaluator = CEC2014(fid, dim)
                    self.assertLessEqual(abs(evaluator(evaluator.optimum_position) - fid * 100), 1e-8)

    def test_domain_validation(self):
        for dim in (0, 1, 2, 20, 199, 201, 30.0, 200.0, True):
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
        CEC2014(29, 200)(np.linspace(-90, 90, 200))
        self.assertEqual(expected, first(x))
        self.assertEqual(state, random.getstate())
        np.testing.assert_array_equal(before, x)
        optimum = first.optimum_position
        optimum[:] = 0
        self.assertFalse(np.all(first.optimum_position == 0))
