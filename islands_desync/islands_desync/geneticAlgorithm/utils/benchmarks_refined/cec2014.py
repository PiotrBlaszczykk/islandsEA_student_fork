"""CEC 2014 Part A functions with the official fixed instance data.

The public suite contains F1--F30. It deliberately
supports the four dimensions in the Part A experimental protocol: 10, 30,
50 and 100, rather than every size accepted by the original C executable.
See RESEARCH.md for discrepancies
between the report's displayed equations and its executable definition.

Only NumPy and the Python standard library are required. There is no random
instance generation, network access, native compilation or jMetal import.
"""

from functools import lru_cache
import hashlib
import json
import math
from numbers import Integral
from pathlib import Path

import numpy as np

from .cec_functions import KERNELS


SELECTED_FIDS = tuple(range(1, 31))
SUPPORTED_DIMENSIONS = (10, 30, 50, 100)
_DATA_FILE = Path(__file__).with_name("data") / "cec2014.npz"
_BASIC_NAMES = (
    "elliptic", "bent_cigar", "discus", "rosenbrock", "ackley",
    "weierstrass", "griewank", "rastrigin", "rastrigin", "schwefel",
    "schwefel", "katsuura", "happycat", "hgbat", "griewank_rosenbrock",
    "expanded_scaffer_f6",
)
_HYBRIDS = {
    17: ((0.3, 0.3, 0.4), ("schwefel", "rastrigin", "elliptic")),
    18: ((0.3, 0.3, 0.4), ("bent_cigar", "hgbat", "rastrigin")),
    19: ((0.2, 0.2, 0.3, 0.3), ("griewank", "weierstrass", "rosenbrock", "expanded_scaffer_f6")),
    20: ((0.2, 0.2, 0.3, 0.3), ("hgbat", "discus", "griewank_rosenbrock", "rastrigin")),
    21: ((0.1, 0.2, 0.2, 0.2, 0.3), ("expanded_scaffer_f6", "hgbat", "rosenbrock", "schwefel", "elliptic")),
    22: ((0.1, 0.2, 0.2, 0.2, 0.3), ("katsuura", "happycat", "griewank_rosenbrock", "schwefel", "ackley")),
}

# (kernels, numerator, divisors, sigmas, indices of unrotated components).
# Keep the reference arithmetic numerator * fit / divisor, including F23's
# 1e30 divisor. All component shifts also serve as their weight centres.
_COMPOSITIONS = {
    23: (("rosenbrock", "elliptic", "bent_cigar", "discus", "elliptic"),
         10000., (1e4, 1e10, 1e30, 1e10, 1e10), (10., 20., 30., 40., 50.), (4,)),
    24: (("schwefel", "rastrigin", "hgbat"),
         1., (1., 1., 1.), (20., 20., 20.), (0,)),
    25: (("schwefel", "rastrigin", "elliptic"),
         1000., (4e3, 1e3, 1e10), (10., 30., 50.), ()),
    26: (("schwefel", "happycat", "elliptic", "weierstrass", "griewank"),
         1000., (4e3, 1e3, 1e10, 400., 100.), (10., 10., 10., 10., 10.), ()),
    27: (("hgbat", "rastrigin", "schwefel", "weierstrass", "elliptic"),
         10000., (1000., 1e3, 4e3, 400., 1e10), (10., 10., 10., 20., 20.), ()),
    28: (("griewank_rosenbrock", "happycat", "schwefel", "expanded_scaffer_f6", "elliptic"),
         10000., (4e3, 1e3, 4e3, 2e7, 1e10), (10., 20., 30., 40., 50.), ()),
}


@lru_cache(maxsize=1)
def _verified_provenance():
    manifest = json.loads(_DATA_FILE.with_name("manifest.json").read_text(encoding="utf-8"))
    if hashlib.sha256(_DATA_FILE.read_bytes()).hexdigest() != manifest["data_sha256"]:
        raise RuntimeError("CEC2014 data checksum mismatch; restore data from the pinned archive")
    return manifest


@lru_cache(maxsize=None)
def _load_instance(fid, dimension):
    """Read only the requested arrays; cache within the worker process."""
    _verified_provenance()
    components = len(_COMPOSITIONS[fid][0]) if fid in _COMPOSITIONS else 3 if fid >= 29 else 1
    try:
        with np.load(_DATA_FILE, allow_pickle=False) as source:
            shifts = np.array(source[f"shift_{fid}"][:components, :dimension], dtype=np.float64)
            matrices = np.array(source[f"matrix_{fid}_{dimension}"][:components], dtype=np.float64)
            shuffles = None
            if 17 <= fid <= 22 or fid >= 29:
                raw_shuffle = source[f"shuffle_{fid}_{dimension}"][:components]
                if raw_shuffle.dtype.kind not in "iu":
                    raise ValueError("CEC shuffle data must contain integers")
                shuffles = np.array(raw_shuffle, dtype=np.int64) - 1
    except (OSError, KeyError, ValueError, IndexError) as error:
        raise RuntimeError(f"Cannot load official CEC2014 F{fid}, D={dimension} from {_DATA_FILE}") from error
    if shifts.shape != (components, dimension) or matrices.shape != (components, dimension, dimension):
        raise RuntimeError("Invalid shape in the bundled CEC2014 instance data")
    if not np.all(np.isfinite(shifts)) or not np.all(np.isfinite(matrices)):
        raise RuntimeError("Non-finite value in the bundled CEC2014 instance data")
    if np.any(np.abs(shifts) > 100.0):
        raise RuntimeError("CEC2014 shift lies outside the declared search domain")
    if shuffles is not None:
        if shuffles.shape != (components, dimension) or not np.all(np.sort(shuffles, axis=1) == np.arange(dimension)):
            raise RuntimeError("CEC2014 shuffle must be a permutation of 1,...,D in source data")
        shuffles.setflags(write=False)
    shifts.setflags(write=False)
    matrices.setflags(write=False)
    return shifts, matrices, shuffles


def _basic(name, x, shift=None, matrix=None):
    kernel, scale = KERNELS[name]
    z = (x - shift) * scale if shift is not None else x * scale
    if matrix is not None:
        z = matrix @ z
    return kernel(z)


@lru_cache(maxsize=None)
def _group_slices(fid, dimension):
    proportions, names = _HYBRIDS[fid]
    sizes = [math.ceil(p * dimension) for p in proportions[:-1]]
    sizes.append(dimension - sum(sizes))
    if any(size <= 0 for size in sizes):
        raise ValueError("Hybrid dimension produces an empty subcomponent")
    offset = 0
    groups = []
    for name, size in zip(names, sizes):
        groups.append((name, slice(offset, offset + size)))
        offset += size
    return tuple(groups)


def _hybrid(fid, x, shift, matrix, shuffle):
    # Official hf01--hf06 rotate the entire shifted vector first, then shuffle;
    # the basic kernels apply their own rates, without further shift/rotation.
    permuted = (matrix @ (x - shift))[shuffle]
    return sum(_basic(name, permuted[group]) for name, group in _group_slices(fid, x.size))


def _composition_weights(x, shifts, sigmas):
    displacement = x - shifts
    squared_distances = np.sum(displacement * displacement, axis=1)
    weights = np.empty(shifts.shape[0], dtype=np.float64)
    nonzero = squared_distances != 0.0
    distances = squared_distances[nonzero]
    weights[nonzero] = np.sqrt(1.0 / distances) * np.exp(-distances / 2.0 / x.size / (sigmas[nonzero] ** 2))
    # cf_cal uses a finite sentinel; preserve it rather than clipping distances
    # to an arbitrary epsilon, which changes neighbourhoods of component optima.
    weights[~nonzero] = 1.0e99
    if float(np.max(weights)) == 0.0:
        weights.fill(1.0)
    return weights / np.sum(weights)


class CEC2014:
    """One fixed, bounded CEC 2014 instance, evaluated as a minimization task.

    ``CEC2014(fid=1, dimension=30)(x)`` returns the biased objective (100 for
    F1 at its shifted optimum), not the error relative to the optimum.
    Input must be a real numeric vector of exactly ``dimension`` finite values
    in [-100, 100]. Invalid inputs raise; they are never flattened, clipped or
    converted into a silent infinity. Calls do not mutate the input or share
    temporary work buffers, so interleaved evaluation of instances is safe.
    """

    bounds = (-100.0, 100.0)

    def __init__(self, fid, dimension):
        if isinstance(fid, (bool, np.bool_)) or not isinstance(fid, Integral) or fid not in SELECTED_FIDS:
            raise ValueError(f"fid must be one of {SELECTED_FIDS}")
        if isinstance(dimension, (bool, np.bool_)) or not isinstance(dimension, Integral) or dimension not in SUPPORTED_DIMENSIONS:
            raise ValueError(f"CEC2014 dimension must be one of {SUPPORTED_DIMENSIONS}")
        self.fid = int(fid)
        self.dimension = int(dimension)
        self.optimum_value = float(100 * self.fid)
        self._shifts, self._matrices, self._shuffles = _load_instance(self.fid, self.dimension)

    @property
    def optimum_position(self):
        """A copy of the first official shift vector (the global optimum)."""
        return self._shifts[0].copy()

    def metadata(self):
        source = _verified_provenance()
        return {"cec_function_id": self.fid, "dimension": self.dimension,
                "optimum_value": self.optimum_value, "bounds": list(self.bounds),
                "objective_direction": "minimize", "data_sha256": source["data_sha256"],
                "source_commit": source["commit"], "source_archive": source["archive_url"],
                "instance": "official fixed CEC2014 Part A data"}

    def __call__(self, x):
        vector = np.asarray(x)
        if vector.shape != (self.dimension,):
            raise ValueError(f"Expected a vector of shape ({self.dimension},), got {vector.shape}")
        if vector.dtype.kind not in "iuf":
            raise ValueError("CEC2014 input must contain real numeric coordinates")
        vector = np.asarray(vector, dtype=np.float64)
        if not np.all(np.isfinite(vector)):
            raise ValueError("CEC2014 input must contain only finite coordinates")
        if np.any(vector < self.bounds[0]) or np.any(vector > self.bounds[1]):
            raise ValueError("CEC2014 coordinates must lie in [-100, 100]")
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            value = self._evaluate(vector) + self.optimum_value
        if not math.isfinite(value):
            raise FloatingPointError(f"CEC2014 F{self.fid}, D={self.dimension} produced a non-finite objective")
        return float(value)

    def _evaluate(self, x):
        if self.fid <= 16:
            matrix = None if self.fid in (8, 10) else self._matrices[0]
            return _basic(_BASIC_NAMES[self.fid - 1], x, self._shifts[0], matrix)
        if self.fid in _HYBRIDS:
            return _hybrid(self.fid, x, self._shifts[0], self._matrices[0], self._shuffles[0])
        if self.fid in _COMPOSITIONS:
            names, numerator, divisors, sigmas, unrotated = _COMPOSITIONS[self.fid]
            values = []
            for i, (name, divisor) in enumerate(zip(names, divisors)):
                matrix = None if i in unrotated else self._matrices[i]
                values.append(numerator * _basic(name, x, self._shifts[i], matrix) / divisor + 100.0 * i)
            weights = _composition_weights(x, self._shifts, np.asarray(sigmas))
        else:  # F29/F30 compose unbiased hybrids with their OWN instance data.
            hybrids = (17, 18, 19) if self.fid == 29 else (20, 21, 22)
            values = [
                _hybrid(fid, x, self._shifts[i], self._matrices[i], self._shuffles[i]) + 100.0 * i
                for i, fid in enumerate(hybrids)
            ]
            weights = _composition_weights(x, self._shifts, np.array([10., 30., 50.]))
        return float(np.sum(weights * values))
