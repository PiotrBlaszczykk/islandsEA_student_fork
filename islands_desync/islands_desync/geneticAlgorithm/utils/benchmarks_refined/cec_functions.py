"""Numerical kernels for the CEC 2014 Part A functions.

These are zero-centred *CEC kernels*, including the internal translations of
Rosenbrock, HappyCat and HGBat. Scaling, instance shifts and rotations are
applied by :mod:`cec2014`. Definitions follow Liang's official C distribution
(December 2013), not formulas from a third-party benchmark library.
"""

from functools import lru_cache
import math

import numpy as np


_PI2 = 2.0 * math.pi
_WEIER_A = 0.5 ** np.arange(21, dtype=np.float64)
_WEIER_ANGULAR = _PI2 * 3.0 ** np.arange(21, dtype=np.float64)
_WEIER_ORIGIN = float(np.sum(_WEIER_A * np.cos(_WEIER_ANGULAR * 0.5)))
_KATSUURA_POWERS = 2.0 ** np.arange(1, 33, dtype=np.float64)


@lru_cache(maxsize=None)
def _elliptic_weights(dimension):
    if dimension < 2:
        raise ValueError("CEC elliptic requires at least two coordinates")
    values = 10.0 ** (6.0 * np.arange(dimension) / (dimension - 1))
    values.setflags(write=False)
    return values


def elliptic(z):
    return float(np.sum(_elliptic_weights(z.size) * z * z))


def bent_cigar(z):
    return float(z[0] * z[0] + np.sum(1.0e6 * z[1:] * z[1:]))


def discus(z):
    return float(1.0e6 * z[0] * z[0] + np.sum(z[1:] * z[1:]))


def rosenbrock(z):
    z = z + 1.0
    residual = z[:-1] * z[:-1] - z[1:]
    return float(np.sum(100.0 * residual * residual + (z[:-1] - 1.0) ** 2))


def ackley(z):
    return float(
        math.e - 20.0 * math.exp(-0.2 * math.sqrt(float(np.sum(z * z)) / z.size))
        - math.exp(float(np.sum(np.cos(_PI2 * z))) / z.size) + 20.0
    )


def weierstrass(z):
    terms = _WEIER_A * np.cos((z[:, None] + 0.5) * _WEIER_ANGULAR)
    return float(np.sum(np.sum(terms, axis=1)) - z.size * _WEIER_ORIGIN)


def griewank(z):
    return float(
        1.0 + np.sum(z * z) / 4000.0
        - np.prod(np.cos(z / np.sqrt(np.arange(1, z.size + 1))))
    )


def rastrigin(z):
    return float(np.sum(z * z - 10.0 * np.cos(_PI2 * z) + 10.0))


def schwefel(z):
    """Modified Schwefel, with both outside-500 branches from the C code."""
    z = z + 4.209687462275036e2
    values = -z * np.sin(np.sqrt(np.abs(z)))
    above = z > 500.0
    below = z < -500.0
    if np.any(above):
        wrapped = 500.0 - np.fmod(z[above], 500.0)
        penalty = (z[above] - 500.0) / 100.0
        values[above] = -wrapped * np.sin(np.sqrt(wrapped)) + penalty * penalty / z.size
    if np.any(below):
        remainder = np.fmod(np.abs(z[below]), 500.0)
        penalty = (z[below] + 500.0) / 100.0
        values[below] = -(-500.0 + remainder) * np.sin(np.sqrt(500.0 - remainder))
        values[below] += penalty * penalty / z.size
    return float(np.sum(values) + 4.189828872724338e2 * z.size)


def katsuura(z):
    scaled = z[:, None] * _KATSUURA_POWERS
    # The reference uses floor(t + 0.5), not Python's ties-to-even round.
    residuals = np.abs(scaled - np.floor(scaled + 0.5)) / _KATSUURA_POWERS
    totals = np.sum(residuals, axis=1)
    product = np.prod((1.0 + np.arange(1, z.size + 1) * totals) ** (10.0 / z.size ** 1.2))
    factor = 10.0 / z.size / z.size
    return float(product * factor - factor)


def happycat(z):
    z = z - 1.0
    squared = float(np.sum(z * z))
    total = float(np.sum(z))
    return abs(squared - z.size) ** 0.25 + (0.5 * squared + total) / z.size + 0.5


def hgbat(z):
    z = z - 1.0
    squared = float(np.sum(z * z))
    total = float(np.sum(z))
    return math.sqrt(abs(squared * squared - total * total)) + (0.5 * squared + total) / z.size + 0.5


def griewank_rosenbrock(z):
    z = z + 1.0
    residual = z * z - np.roll(z, -1)
    rosen = 100.0 * residual * residual + (z - 1.0) ** 2
    return float(np.sum(rosen * rosen / 4000.0 - np.cos(rosen) + 1.0))


def expanded_scaffer_f6(z):
    squared = z * z + np.roll(z, -1) ** 2
    sine = np.sin(np.sqrt(squared))
    denominator = 1.0 + 0.001 * squared
    return float(np.sum(0.5 + (sine * sine - 0.5) / (denominator * denominator)))


# Rate is applied before rotation, matching sr_func exactly. It also applies
# inside hybrids when shift and rotation flags are both zero.
KERNELS = {
    "elliptic": (elliptic, 1.0),
    "bent_cigar": (bent_cigar, 1.0),
    "discus": (discus, 1.0),
    "rosenbrock": (rosenbrock, 2.048 / 100.0),
    "ackley": (ackley, 1.0),
    "weierstrass": (weierstrass, 0.5 / 100.0),
    "griewank": (griewank, 600.0 / 100.0),
    "rastrigin": (rastrigin, 5.12 / 100.0),
    "schwefel": (schwefel, 1000.0 / 100.0),
    "katsuura": (katsuura, 5.0 / 100.0),
    "happycat": (happycat, 5.0 / 100.0),
    "hgbat": (hgbat, 5.0 / 100.0),
    "griewank_rosenbrock": (griewank_rosenbrock, 5.0 / 100.0),
    "expanded_scaffer_f6": (expanded_scaffer_f6, 1.0),
}
