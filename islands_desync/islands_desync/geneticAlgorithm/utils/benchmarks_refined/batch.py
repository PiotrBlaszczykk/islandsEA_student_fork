"""Explicit float64 batch backends for the same 30 CEC + 10 binary objectives.

Keep a backend alive in the GPU-owning actor. Call prepare() before timing to
upload immutable instance data once. evaluate_batch accepts HOST arrays and
returns HOST arrays in the same row order, with one H2D and one D2H per call.
No CPU fallback is hidden in CupyBatchBackend. No Ray actors/GA are started here.
"""
from numbers import Integral
import time

import numpy as np

from . import CONTINUOUS_BENCHMARKS, SUITE_VERSION, create_evaluator
from .batch_kernels import BatchKernels
from .cec2014 import _BASIC_NAMES, _COMPOSITIONS, _HYBRIDS, _group_slices
from .cec_functions import KERNELS
from .discrete import DEFAULT_INSTANCE_SEED
from .provenance import implementation_sha256

BATCH_VERSION = "1.0.0"


class _Instance:
    def __init__(self, key, dimension, seed, xp, kernels):
        self.key, self.xp, self.kernels = key, xp, kernels
        self.scalar = create_evaluator(key, dimension, instance_seed=seed)
        self.dimension = self.scalar.dimension
        self.continuous = key in CONTINUOUS_BENCHMARKS
        if self.continuous:
            self.fid = self.scalar.fid
            self.shifts = xp.asarray(self.scalar._shifts)
            self.matrices_t = tuple(xp.asarray(np.ascontiguousarray(m.T)) for m in self.scalar._matrices)
            self.shuffles = None if self.scalar._shuffles is None else tuple(xp.asarray(s) for s in self.scalar._shuffles)
            kernels.prepare(dimension)
            hybrid_ids = (self.fid,) if self.fid in _HYBRIDS else (17, 18, 19) if self.fid == 29 else (20, 21, 22) if self.fid == 30 else ()
            for fid in hybrid_ids:
                for _, group in _group_slices(fid, dimension):
                    kernels.prepare(group.stop - group.start)
            sigmas = _COMPOSITIONS[self.fid][3] if self.fid in _COMPOSITIONS else (10., 30., 50.)
            self.sigmas = xp.asarray(np.asarray(sigmas, dtype=np.float64)) if self.fid >= 23 else None
        else:
            self.index = self.scalar.index
            # Worst-case LABS energy for constant spins. Avoid silent int64 overflow.
            if self.index == 1 and dimension * (dimension - 1) * (2 * dimension - 1) // 6 > np.iinfo(np.int64).max:
                raise ValueError("LABS dimension exceeds exact int64 batch energy capacity")
            self.tables = None if self.scalar._tables is None else xp.asarray(self.scalar._tables)
            self.positions = xp.asarray(np.arange(dimension, dtype=np.int64))

    def basic(self, name, x, component=None, rotate=True):
        scale = KERNELS[name][1]
        z = x * scale if component is None else (x - self.shifts[component]) * scale
        if component is not None and rotate:
            z = z @ self.matrices_t[component]
        return self.kernels.evaluate(name, z)

    def hybrid(self, fid, x, component):
        permuted = ((x - self.shifts[component]) @ self.matrices_t[component])[:, self.shuffles[component]]
        return sum(self.basic(name, permuted[:, group]) for name, group in _group_slices(fid, self.dimension))

    def weights(self, x):
        xp = self.xp
        delta = x[:, None, :] - self.shifts[None, :, :]
        distances = xp.sum(delta * delta, axis=-1)
        # Exact-zero sentinel, without invalid/divide-by-zero on inactive rows.
        safe = xp.where(distances == 0.0, 1.0, distances)
        values = xp.sqrt(1.0 / safe) * xp.exp(-safe / 2.0 / self.dimension / self.sigmas ** 2)
        values = xp.where(distances == 0.0, 1.0e99, values)
        values = xp.where(xp.max(values, axis=-1, keepdims=True) == 0.0, 1.0, values)
        return values / xp.sum(values, axis=-1, keepdims=True)

    def evaluate(self, x):
        xp = self.xp
        if not self.continuous:
            return self.binary(x).astype(xp.float64, copy=False)
        fid = self.fid
        if fid <= 16:
            value = self.basic(_BASIC_NAMES[fid - 1], x, 0, rotate=fid not in (8, 10))
        elif fid in _HYBRIDS:
            value = self.hybrid(fid, x, 0)
        else:
            if fid in _COMPOSITIONS:
                names, numerator, divisors, _, unrotated = _COMPOSITIONS[fid]
                components = [numerator * self.basic(name, x, i, rotate=i not in unrotated) / divisor + 100.0 * i
                              for i, (name, divisor) in enumerate(zip(names, divisors))]
            else:
                hybrids = (17, 18, 19) if fid == 29 else (20, 21, 22)
                components = [self.hybrid(h, x, i) + 100.0 * i for i, h in enumerate(hybrids)]
            value = xp.sum(self.weights(x) * xp.stack(components, axis=-1), axis=-1)
        return value + self.scalar.optimum_value

    def binary(self, bits):
        xp, n, index = self.xp, self.dimension, self.index
        if index == 1:
            spins = 2 * bits - 1
            energy = xp.zeros(bits.shape[0], dtype=xp.int64)
            for lag in range(1, n):
                correlation = xp.sum(spins[:, :-lag] * spins[:, lag:], axis=-1, dtype=xp.int64)
                energy += correlation * correlation
            return -(float(n * n) / (2.0 * energy))
        if index in (2, 8, 9):
            block = self.scalar.block_size
            ones = xp.sum(bits.reshape(bits.shape[0], n // block, block), axis=-1)
            if index == 9:
                return -block * xp.sum(ones == block, axis=-1)
            return -xp.sum(xp.where(ones == block, block, block - 1 - ones), axis=-1)
        if index == 3:
            pattern = xp.zeros(bits.shape, dtype=xp.int64)
            for offset in range(5):
                pattern = (pattern << 1) | xp.roll(bits, -offset, axis=-1)
            # Same tables/bit order; a parallel reduction may change last bits
            # relative to scalar's sequential sum (documented NK tolerance).
            return -xp.sum(self.tables[self.positions[None, :], pattern], axis=-1) / n
        if index == 4:
            return -xp.sum(bits, axis=-1)
        if index == 5:
            return -(n - xp.sum(bits, axis=-1))
        if index == 6:
            return -xp.min(xp.where(bits == 0, self.positions, n), axis=-1)
        if index == 7:
            matches = xp.sum(bits == (self.positions % 2 == 0), axis=-1)
            return -xp.maximum(matches, n - matches)
        return -xp.sum(bits != xp.roll(bits, -1, axis=-1), axis=-1)


class NumpyBatchBackend:
    """Reusable batch evaluator; real inputs are promoted to float64/int64.

    Empty [0,D] batches are valid; rank, domains, dtype and the resource limit
    are checked before candidate transfer. Instances are cached by name/D/seed.
    Context/routing IDs belong to the caller; row order is never changed.
    """
    backend_name = "numpy-batch"

    def __init__(self, *, max_batch_size=8192):
        if isinstance(max_batch_size, bool) or not isinstance(max_batch_size, Integral) or max_batch_size < 1:
            raise ValueError("max_batch_size must be a positive integer")
        self.max_batch_size = int(max_batch_size)
        self.xp = np
        self._instances = {}
        self._kernels = None
        self.last_profile = None

    def prepare(self, problem_id, dimension, *, instance_seed=DEFAULT_INSTANCE_SEED):
        key = str(problem_id).strip().lower()
        # Validate even cache hits, so True/30.0 cannot alias integer cache keys.
        if isinstance(dimension, (bool, np.bool_)) or not isinstance(dimension, Integral):
            raise ValueError("dimension must be an integer")
        if isinstance(instance_seed, (bool, np.bool_)) or not isinstance(instance_seed, Integral) or instance_seed < 0:
            raise ValueError("instance_seed must be a nonnegative integer")
        cache_key = (key, int(dimension), int(instance_seed))
        if cache_key not in self._instances:
            if self._kernels is None:
                self._kernels = BatchKernels(self.xp)
            self._instances[cache_key] = _Instance(key, int(dimension), int(instance_seed), self.xp, self._kernels)
        return cache_key

    def metadata(self, problem_id, dimension, *, instance_seed=DEFAULT_INSTANCE_SEED):
        key = self.prepare(problem_id, dimension, instance_seed=instance_seed)
        result = self._instances[key].scalar.metadata()
        result.update(name=key[0], suite="benchmarks_refined", suite_version=SUITE_VERSION,
                      backend=self.backend_name, batch_version=BATCH_VERSION,
                      implementation_sha256=implementation_sha256(), output_dtype="float64",
                      max_batch_size=self.max_batch_size, input_location="host", output_location="host")
        return result

    def _input(self, problem_id, vectors, seed):
        # Never accidentally copy a device array back to host just to validate.
        if hasattr(vectors, "__cuda_array_interface__"):
            raise ValueError("evaluate_batch requires host inputs, not device arrays")
        values = np.asarray(vectors)
        if values.ndim != 2:
            raise ValueError("Expected a [batch, dimension] array")
        if values.shape[0] > self.max_batch_size:
            raise ValueError("Batch exceeds max_batch_size; partition it in the caller")
        key = self.prepare(problem_id, values.shape[1], instance_seed=seed)
        instance = self._instances[key]
        kinds = "iuf" if instance.continuous else "biuf"
        if values.dtype.kind not in kinds or not np.all(np.isfinite(values)):
            raise ValueError("Input must contain finite real coordinates (or binary 0/1)")
        if instance.continuous:
            if np.any(values < -100.0) or np.any(values > 100.0):
                raise ValueError("CEC coordinates must lie in [-100,100]")
        elif not np.all((values == 0) | (values == 1)):
            raise ValueError("Binary input must contain only 0/1")
        return instance, np.ascontiguousarray(values, dtype=np.float64 if instance.continuous else np.int64)

    def evaluate_batch(self, problem_id, vectors, *, instance_seed=DEFAULT_INSTANCE_SEED):
        self.last_profile = None
        started = time.perf_counter()
        instance, host = self._input(problem_id, vectors, instance_seed)
        prepared = time.perf_counter()
        if not host.shape[0]:
            result = np.empty(0, dtype=np.float64)
            transfer = {"h2d_count": 0, "d2h_count": 0}
        else:
            result, transfer = self._evaluate_host(instance, host)
        if result.shape != (host.shape[0],) or result.dtype != np.dtype("float64") or not np.all(np.isfinite(result)):
            raise FloatingPointError("Batch backend returned invalid/non-finite objectives")
        self.last_profile = dict(transfer, batch_size=host.shape[0], dimension=host.shape[1],
                                 backend=self.backend_name, prepare_and_validation_seconds=prepared-started,
                                 call_seconds=time.perf_counter()-started)
        return result

    def _evaluate_host(self, instance, host):
        started = time.perf_counter()
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            result = np.asarray(instance.evaluate(host), dtype=np.float64)
        return result, {"compute_seconds": time.perf_counter()-started, "h2d_count": 0, "d2h_count": 0}


class CupyBatchBackend(NumpyBatchBackend):
    """Instantiate inside the long-lived Ray num_gpus=1 actor only.

    NumPy imports remain usable without CuPy installed. Device selection is
    logical within CUDA_VISIBLE_DEVICES. Calls run on one private stream and
    must not be invoked concurrently on a single backend instance.
    """
    backend_name = "athena-cupy"

    def __init__(self, *, max_batch_size=8192):
        super().__init__(max_batch_size=max_batch_size)
        import cupy as cp
        if cp.cuda.runtime.getDeviceCount() < 1:
            raise RuntimeError("No CUDA device available; no silent CPU fallback")
        self.xp = cp
        self.device_id = cp.cuda.Device().id
        self.stream = cp.cuda.Stream(non_blocking=True)

    def prepare(self, problem_id, dimension, *, instance_seed=DEFAULT_INSTANCE_SEED):
        with self.xp.cuda.Device(self.device_id), self.stream:
            return super().prepare(problem_id, dimension, instance_seed=instance_seed)

    def _evaluate_host(self, instance, host):
        cp = self.xp
        with cp.cuda.Device(self.device_id), self.stream:
            before_h2d, after_h2d, after_kernel = (cp.cuda.Event() for _ in range(3))
            before_h2d.record(self.stream)
            device = cp.asarray(host)
            after_h2d.record(self.stream)
            values = instance.evaluate(device)
            after_kernel.record(self.stream)
            d2h_started = time.perf_counter()
            # CuPy 10.6 asnumpy is blocking. This is the only host read; it
            # completes the private stream before events are queried.
            result = cp.asnumpy(values, stream=self.stream)
            return result, {"h2d_count": 1, "d2h_count": 1,
                            "h2d_device_seconds": cp.cuda.get_elapsed_time(before_h2d, after_h2d) / 1000.0,
                            "kernel_device_seconds": cp.cuda.get_elapsed_time(after_h2d, after_kernel) / 1000.0,
                            "d2h_and_pending_compute_wait_seconds": time.perf_counter()-d2h_started}
