"""Deterministic numerical checks usable locally and inside the A100 actor.

This is validation, not a GA run or a claim of accelerator speedup. Reference
values come from the unchanged scalar evaluators and committed C golden data.
"""
from collections import defaultdict
import gzip
import json
from pathlib import Path
import random

import numpy as np

from . import BENCHMARKS, CONTINUOUS_BENCHMARKS, create_evaluator
from .cec2014 import SUPPORTED_DIMENSIONS


def tolerances(name):
    if name in CONTINUOUS_BENCHMARKS:
        # Same C-oracle tolerances as the existing scalar reference tests.
        return 1e-10, 1e-8
    if name in ("b01_labs_binary", "b03_nk_k4"):
        # LABS divides an exact int64 energy; NK sums float64 tables in parallel.
        return 2e-14, 2e-14
    return 0.0, 0.0


def golden_groups():
    directory = Path(__file__).with_name("tests") / "reference"
    groups = defaultdict(list)
    for filename in ("cec2014_golden.json.gz", "cec2014_d200_golden.json.gz"):
        data = json.loads(gzip.decompress((directory / filename).read_bytes()))
        for case in data["cases"]:
            groups[(CONTINUOUS_BENCHMARKS[case["fid"] - 1], case["dimension"])].append(case)
    return groups


def validate_backend(backend, *, dimensions=SUPPORTED_DIMENSIONS, binary_dimensions=(60, 200), large_batch=256):
    if not 1 <= large_batch <= backend.max_batch_size:
        raise ValueError("large_batch must fit the backend batch limit")
    python_rng_before, numpy_rng_before = random.getstate(), np.random.get_state()
    rng = np.random.RandomState(20260914)
    records = []
    golden = golden_groups()
    for name in BENCHMARKS:
        continuous = name in CONTINUOUS_BENCHMARKS
        for dimension in dimensions if continuous else binary_dimensions:
            scalar = create_evaluator(name, dimension)
            backend.prepare(name, dimension)
            rtol, atol = tolerances(name)
            record = {"name": name, "dimension": dimension, "rtol": rtol, "atol": atol,
                      "checked_rows": 0, "max_absolute_error": 0.0, "max_scaled_error": 0.0,
                      "metadata": backend.metadata(name, dimension)}

            def check(vectors, expected=None, label="scalar"):
                vectors = np.asarray(vectors)
                before = vectors.copy()
                reference = np.asarray([scalar(row) for row in vectors]) if expected is None else np.asarray(expected)
                values = backend.evaluate_batch(name, vectors)
                np.testing.assert_array_equal(vectors, before)
                if values.dtype != np.dtype("float64") or values.shape != (len(vectors),):
                    raise AssertionError(f"{name}/{dimension}: invalid output contract")
                if not np.all(np.isfinite(values)):
                    raise AssertionError(f"{name}/{dimension}: nonfinite output")
                np.testing.assert_allclose(values, reference, rtol=rtol, atol=atol,
                                           err_msg=f"{backend.backend_name} {name} D={dimension} {label}")
                if len(values):
                    delta = np.abs(values-reference)
                    record["max_absolute_error"] = max(record["max_absolute_error"], float(np.max(delta)))
                    record["max_scaled_error"] = max(record["max_scaled_error"], float(np.max(delta / np.maximum(np.abs(reference), 1.0))))
                record["checked_rows"] += len(values)
                return values

            cases = golden.get((name, dimension), [])
            if cases:
                check([c["x"] for c in cases], [c["expected"] for c in cases], "committed C oracle")
            if scalar.optimum_position is not None:
                check(np.asarray(scalar.optimum_position)[None, :], [scalar.optimum_value], "optimum")
            for size in (1, 4, 16, 32):
                vectors = rng.uniform(-100, 100, (size, dimension)) if continuous else rng.randint(0, 2, (size, dimension))
                baseline = check(vectors)
                # Deliberately interleave another problem, then permute rows.
                other = "b04_onemax" if continuous else "r01_elliptic"
                backend.evaluate_batch(other, np.zeros((1, 200)))
                np.testing.assert_array_equal(backend.evaluate_batch(name, vectors), baseline)
                check(vectors[::-1], baseline[::-1], "row order")
            edges = np.stack([np.full(dimension, -100 if continuous else 0), np.full(dimension, 100 if continuous else 1)])
            check(edges, label="domain edges")
            check(np.empty((0, dimension)), label="empty batch")
            if backend.last_profile["h2d_count"] or backend.last_profile["d2h_count"]:
                raise AssertionError("An empty batch must not transfer candidates/results")
            for dtype in ((np.float32, np.int64) if continuous else (bool, np.uint8, np.int64, np.float64)):
                check(edges.astype(dtype), label=f"input dtype {dtype}")
            invalid = [np.zeros(dimension), np.zeros((1, 0)), np.full((1, dimension), np.nan),
                       np.full((1, dimension), np.inf), np.full((1, dimension), 1j),
                       np.full((1, dimension), "1"), np.full((1, dimension), -101 if continuous else -1),
                       np.full((1, dimension), 101 if continuous else 0.5)]
            if continuous:
                invalid += [np.zeros((1, 20)), np.ones((1, dimension), dtype=bool)]
            elif scalar.block_size:
                invalid.append(np.zeros((1, dimension + 1)))
            for vectors in invalid:
                try:
                    backend.evaluate_batch(name, vectors)
                except ValueError:
                    pass
                else:
                    raise AssertionError(f"{name}/{dimension}: accepted invalid input {vectors.shape}/{vectors.dtype}")
            record["rejected_invalid_inputs"] = len(invalid)
            large = rng.uniform(-100, 100, (large_batch, dimension)) if continuous else rng.randint(0, 2, (large_batch, dimension))
            large_before = large.copy()
            large_values = backend.evaluate_batch(name, large)
            np.testing.assert_array_equal(large, large_before)
            if large_values.dtype != np.dtype("float64") or large_values.shape != (large_batch,) or not np.all(np.isfinite(large_values)):
                raise AssertionError(f"{name}/{dimension}: invalid large batch output")
            selected = np.unique([0, large_batch // 2, large_batch - 1])
            np.testing.assert_allclose(large_values[selected], [scalar(large[i]) for i in selected], rtol=rtol, atol=atol)
            record["large_batch"] = large_batch
            record["large_batch_profile"] = backend.last_profile
            record["checked_rows"] += len(selected)
            if len(record["metadata"]["implementation_sha256"]) != 64:
                raise AssertionError("Missing implementation provenance")
            hash_key = "data_sha256" if continuous else "definition_sha256"
            if record["metadata"][hash_key] != scalar.metadata()[hash_key]:
                raise AssertionError(f"{name}/{dimension}: instance provenance mismatch")
            records.append(record)
    try:
        backend.evaluate_batch("b04_onemax", np.zeros((backend.max_batch_size + 1, 1)))
    except ValueError:
        pass
    else:
        raise AssertionError("Backend did not enforce its batch size cap")
    if python_rng_before != random.getstate():
        raise AssertionError("Backend modified the global Python RNG")
    for before, after in zip(numpy_rng_before, np.random.get_state()):
        np.testing.assert_array_equal(before, after)
    return {"status": "passed", "backend": backend.backend_name, "instances": records,
            "benchmark_count": len({r["name"] for r in records}), "instance_count": len(records),
            "checked_rows": sum(r["checked_rows"] for r in records),
            "rejected_invalid_inputs": 1 + sum(r["rejected_invalid_inputs"] for r in records),
            "global_rng_unchanged": True}


def main():
    """Write reproducible local CPU evidence; GPU evidence needs the Ray job."""
    import argparse
    import platform
    import traceback
    from .batch import NumpyBatchBackend
    from .provenance import implementation_sha256

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = {"schema_version": 1, "purpose": "Local CPU batch validation; GPU not executed",
              "python": platform.python_version(), "platform": platform.platform(),
              "numpy": np.__version__, "implementation_sha256": implementation_sha256(),
              "gpu_validated": False}
    try:
        report.update(validate_backend(NumpyBatchBackend()))
    except Exception:
        report.update(status="failed", traceback=traceback.format_exc())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(args.output)
    print(f"CPU batch validation: {report['status']}; report={args.output}")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
