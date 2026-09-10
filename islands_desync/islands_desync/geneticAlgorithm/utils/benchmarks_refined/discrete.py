"""The existing ten binary objectives, validated without redefining them.

These functions are not part of CEC2014. Scores retain the previous d01--d10
minimization convention, including NEGATIVE MERIT (not energy) for LABS and
the same random.Random(20260511) adjacent NK tables. No evaluation uses RNG.
"""
import hashlib
import json
from functools import lru_cache
from numbers import Integral
import random

import numpy as np

DISCRETE_BENCHMARKS = (
    "b01_labs_binary", "b02_trap5", "b03_nk_k4", "b04_onemax",
    "b05_zeromax", "b06_leading_ones", "b07_alternating_bits",
    "b08_trap4", "b09_royal_road4", "b10_maxcut_ring",
)
DESCRIPTIONS = (
    "Low autocorrelation binary sequence (negative merit factor)",
    "Concatenated deceptive trap, block size 5", "Adjacent cyclic NK, K=4",
    "OneMax", "ZeroMax", "LeadingOnes", "Best match to an alternating string",
    "Concatenated deceptive trap, block size 4", "Royal Road R1, block size 4",
    "Max-Cut on a cycle",
)
DEFAULT_INSTANCE_SEED = 20260511


@lru_cache(maxsize=32)
def _nk_tables(dimension, seed):
    # Preserve the legacy generator and traversal exactly.
    rng = random.Random(seed)
    tables = np.array([[rng.random() for _ in range(32)] for _ in range(dimension)])
    tables.setflags(write=False)
    return tables


class BinaryBenchmark:
    """A minimization objective on exactly n bits (bool or numeric 0/1).

    Known optima remain None for general LABS and random NK instances. Invalid
    dimensions are rejected, never padded or silently rounded.
    """
    def __init__(self, key, dimension=60, instance_seed=DEFAULT_INSTANCE_SEED):
        if key not in DISCRETE_BENCHMARKS:
            raise KeyError(f"Unknown refined discrete benchmark: {key!r}")
        if isinstance(dimension, (bool, np.bool_)) or not isinstance(dimension, Integral):
            raise ValueError("dimension must be an integer")
        if isinstance(instance_seed, (bool, np.bool_)) or not isinstance(instance_seed, Integral) or instance_seed < 0:
            raise ValueError("instance_seed must be a nonnegative integer")
        self.key = key
        self.dimension = int(dimension)
        self.index = DISCRETE_BENCHMARKS.index(key) + 1
        self.instance_seed = int(instance_seed)
        n = self.dimension
        minimum = 5 if self.index == 3 else 3 if self.index == 10 else 2 if self.index == 1 else 1
        if n < minimum:
            raise ValueError(f"{key} requires dimension >= {minimum}")
        self.block_size = 5 if self.index == 2 else 4 if self.index in (8, 9) else None
        if self.block_size and n % self.block_size:
            raise ValueError(f"{key} requires dimension divisible by {self.block_size}")
        if self.index != 3 and self.instance_seed != DEFAULT_INSTANCE_SEED:
            raise ValueError("instance_seed is only meaningful for NK; other objectives have no random instance")
        self._tables = _nk_tables(n, self.instance_seed) if self.index == 3 else None
        self.optimum_value = None if self.index in (1, 3) else float(-(n - n % 2) if self.index == 10 else -n)

    @property
    def optimum_position(self):
        if self.index in (1, 3):
            return None
        if self.index == 5:
            return np.zeros(self.dimension, dtype=bool)
        if self.index in (7, 10):
            return np.arange(self.dimension) % 2 == 0
        return np.ones(self.dimension, dtype=bool)

    def __call__(self, bits):
        values = np.asarray(bits)
        if values.shape != (self.dimension,):
            raise ValueError(f"Expected {self.dimension} bits, got shape {values.shape}")
        if values.dtype.kind not in "biuf" or not np.all((values == 0) | (values == 1)):
            raise ValueError("Candidate must contain only booleans or numeric 0/1")
        bits = values.astype(np.int64, copy=False)
        n, index = self.dimension, self.index
        if index == 1:
            # Signed int64 avoids uint/bool subtraction; lag n-1 contributes 1.
            spins = 2 * bits - 1
            energy = sum(int(np.dot(spins[:-k], spins[k:])) ** 2 for k in range(1, n))
            return -float(n * n / (2 * energy))
        if index in (2, 8):
            ones = bits.reshape(-1, self.block_size).sum(axis=1)
            return -float(np.where(ones == self.block_size, self.block_size, self.block_size - 1 - ones).sum())
        if index == 3:
            # Match legacy bit order (current bit is most significant).
            score = 0.0
            for start in range(n):
                pattern = 0
                for offset in range(5):
                    pattern = (pattern << 1) | int(bits[(start + offset) % n])
                score += float(self._tables[start, pattern])
            return -(score / n)
        if index == 4:
            return -float(bits.sum())
        if index == 5:
            return -float(n - bits.sum())
        if index == 6:
            zeros = np.flatnonzero(bits == 0)
            return -float(zeros[0] if zeros.size else n)
        if index == 7:
            matches = int(np.count_nonzero(bits == (np.arange(n) % 2 == 0)))
            return -float(max(matches, n - matches))
        if index == 9:
            return -float(self.block_size * np.count_nonzero(np.all(bits.reshape(-1, self.block_size), axis=1)))
        return -float(np.count_nonzero(bits != np.roll(bits, -1)))

    def metadata(self):
        info = {
            "name": self.key, "legacy_name": "d" + self.key[1:],
            "dimension": self.dimension, "objective_direction": "minimize",
            "definition": DESCRIPTIONS[self.index - 1],
            "optimum_value": self.optimum_value, "block_size": self.block_size,
        }
        if self.index == 3:
            info["instance"] = {
                "seed": self.instance_seed, "generator": "Python random.Random(seed).random(), legacy row-major order",
                "k": 4, "neighbours": "i,i+1,...,i+4 modulo n; first bit most significant",
                "tables": self._tables.tolist(),
            }
        canonical = json.dumps(info, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
        info["definition_sha256"] = hashlib.sha256(canonical).hexdigest()
        return info
