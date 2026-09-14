"""Batch-axis kernels shared by NumPy and CuPy; no host reads or RNG.

Scalar kernels remain the independent oracle. Kernel names, scales, hybrid
groups and composition definitions are imported from the canonical modules.
All reductions here are explicitly per candidate, never across candidates.
"""
import math

import numpy as np

from .cec_functions import _WEIER_A, _WEIER_ANGULAR, _WEIER_ORIGIN, _KATSUURA_POWERS


class BatchKernels:
    def __init__(self, xp):
        self.xp = xp
        self.weier_a = xp.asarray(_WEIER_A)
        self.weier_angular = xp.asarray(_WEIER_ANGULAR)
        self.katsuura_powers = xp.asarray(_KATSUURA_POWERS)
        self.constants = {}

    def prepare(self, dimension):
        if dimension not in self.constants:
            indices = np.arange(1, dimension + 1, dtype=np.float64)
            elliptic = 10.0 ** (6.0 * (indices - 1) / (dimension - 1)) if dimension > 1 else indices
            self.constants[dimension] = tuple(self.xp.asarray(a) for a in
                                             (indices, np.sqrt(indices), elliptic))

    def evaluate(self, name, z):
        xp, n = self.xp, z.shape[-1]
        indices, roots, weights = self.constants[n]
        if name == "elliptic":
            return xp.sum(weights * z * z, axis=-1)
        if name == "bent_cigar":
            return z[:, 0] ** 2 + xp.sum(1.0e6 * z[:, 1:] * z[:, 1:], axis=-1)
        if name == "discus":
            return 1.0e6 * z[:, 0] ** 2 + xp.sum(z[:, 1:] ** 2, axis=-1)
        if name == "rosenbrock":
            z = z + 1.0
            residual = z[:, :-1] ** 2 - z[:, 1:]
            return xp.sum(100.0 * residual ** 2 + (z[:, :-1] - 1.0) ** 2, axis=-1)
        if name == "ackley":
            return (math.e - 20.0 * xp.exp(-0.2 * xp.sqrt(xp.sum(z * z, axis=-1) / n))
                    - xp.exp(xp.sum(xp.cos(2.0 * math.pi * z), axis=-1) / n) + 20.0)
        if name == "weierstrass":
            terms = self.weier_a * xp.cos((z[:, :, None] + 0.5) * self.weier_angular)
            return xp.sum(xp.sum(terms, axis=-1), axis=-1) - n * _WEIER_ORIGIN
        if name == "griewank":
            return 1.0 + xp.sum(z * z, axis=-1) / 4000.0 - xp.prod(xp.cos(z / roots), axis=-1)
        if name == "rastrigin":
            return xp.sum(z * z - 10.0 * xp.cos(2.0 * math.pi * z) + 10.0, axis=-1)
        if name == "schwefel":
            z = z + 4.209687462275036e2
            regular = -z * xp.sin(xp.sqrt(xp.abs(z)))
            # Safe values on inactive branches: xp.where evaluates both sides.
            high_z = xp.maximum(z, 500.0)
            wrapped = 500.0 - xp.fmod(high_z, 500.0)
            high = -wrapped * xp.sin(xp.sqrt(wrapped)) + ((high_z - 500.0) / 100.0) ** 2 / n
            low_z = xp.minimum(z, -500.0)
            remainder = xp.fmod(xp.abs(low_z), 500.0)
            low = -(-500.0 + remainder) * xp.sin(xp.sqrt(500.0 - remainder))
            low = low + ((low_z + 500.0) / 100.0) ** 2 / n
            return xp.sum(xp.where(z > 500.0, high, xp.where(z < -500.0, low, regular)), axis=-1) + 4.189828872724338e2 * n
        if name == "katsuura":
            scaled = z[:, :, None] * self.katsuura_powers
            residuals = xp.abs(scaled - xp.floor(scaled + 0.5)) / self.katsuura_powers
            totals = xp.sum(residuals, axis=-1)
            product = xp.prod((1.0 + indices * totals) ** (10.0 / n ** 1.2), axis=-1)
            factor = 10.0 / n / n
            return product * factor - factor
        if name in ("happycat", "hgbat"):
            z = z - 1.0
            squared, total = xp.sum(z * z, axis=-1), xp.sum(z, axis=-1)
            first = xp.abs(squared - n) ** 0.25 if name == "happycat" else xp.sqrt(xp.abs(squared * squared - total * total))
            return first + (0.5 * squared + total) / n + 0.5
        if name == "griewank_rosenbrock":
            z = z + 1.0
            residual = z * z - xp.roll(z, -1, axis=-1)
            rosen = 100.0 * residual * residual + (z - 1.0) ** 2
            return xp.sum(rosen * rosen / 4000.0 - xp.cos(rosen) + 1.0, axis=-1)
        if name == "expanded_scaffer_f6":
            squared = z * z + xp.roll(z, -1, axis=-1) ** 2
            sine = xp.sin(xp.sqrt(squared))
            denominator = 1.0 + 0.001 * squared
            return xp.sum(0.5 + (sine * sine - 0.5) / (denominator * denominator), axis=-1)
        raise KeyError(name)
