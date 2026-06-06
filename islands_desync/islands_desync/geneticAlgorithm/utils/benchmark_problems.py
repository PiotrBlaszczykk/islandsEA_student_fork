import math
import random
from dataclasses import dataclass
from functools import lru_cache
from typing import Callable

import numpy as np
from jmetal.core.problem import BinaryProblem, FloatProblem
from jmetal.core.solution import BinarySolution, FloatSolution


CONTINUOUS_40_BENCHMARKS = [
    "c01_elliptic",
    "c02_bent_cigar",
    "c03_discus",
    "c04_rosenbrock",
    "c05_ackley",
    "c06_weierstrass",
    "c07_griewank",
    "c08_rastrigin",
    "c09_rot_rastrigin",
    "c10_schwefel",
    "c11_rot_schwefel",
    "c12_katsuura",
    "c13_happycat",
    "c14_hgbat",
    "c15_grie_rosen",
    "c16_schaffer_f6",
    "c17_hybrid1",
    "c18_hybrid2",
    "c19_hybrid3",
    "c20_hybrid4",
    "c21_hybrid5",
    "c22_hybrid6",
    "c23_composition1",
    "c24_composition2",
    "c25_composition3",
    "c26_composition4",
    "c27_composition5",
    "c28_composition6",
    "c29_composition7",
    "c30_composition8",
]

DISCRETE_40_BENCHMARKS = [
    "d01_labs_binary",
    "d02_trap5",
    "d03_nk_k4",
    "d04_onemax",
    "d05_zeromax",
    "d06_leading_ones",
    "d07_alternating_bits",
    "d08_trap4",
    "d09_royal_road4",
    "d10_maxcut_ring",
]

SCHEDULED_40_BENCHMARKS = CONTINUOUS_40_BENCHMARKS + DISCRETE_40_BENCHMARKS

GEATBX_OPTIONAL_BENCHMARKS = [
    "g01_sphere",
    "g02_axis_ellipsoid",
    "g03_rotated_ellipsoid",
    "g04_moved_ellipsoid",
    "g05_rosenbrock",
    "g06_rastrigin",
    "g07_schwefel",
    "g08_griewank",
    "g09_sum_power",
    "g10_ackley",
    "g11_langermann",
    "g12_michalewicz",
    "g13_branin",
    "g14_easom",
    "g15_goldstein_price",
    "g16_six_hump_camel",
]


@dataclass(frozen=True)
class BenchmarkInfo:
    name: str
    kind: str
    source: str
    description: str


def normalize_problem_name(name: str) -> str:
    return str(name).strip().lower().replace("-", "_")


def log_prefix(problem_name: str) -> str:
    return normalize_problem_name(problem_name)[:4]


class _FloatBenchmark(FloatProblem):
    def __init__(
        self,
        name: str,
        number_of_variables: int,
        lower_bound,
        upper_bound,
        evaluator: Callable[[np.ndarray], float],
    ):
        super().__init__()
        self._name = name
        self.number_of_variables = int(number_of_variables)
        self.number_of_objectives = 1
        self.number_of_constraints = 0
        self.obj_directions = [self.MINIMIZE]
        self.obj_labels = ["f(x)"]
        self.lower_bound = _expand_bounds(lower_bound, self.number_of_variables)
        self.upper_bound = _expand_bounds(upper_bound, self.number_of_variables)
        self._evaluator = evaluator

        FloatSolution.lower_bound = self.lower_bound
        FloatSolution.upper_bound = self.upper_bound

    def evaluate(self, solution: FloatSolution) -> FloatSolution:
        x = np.asarray(solution.variables, dtype=float)
        value = float(self._evaluator(x))
        if math.isnan(value):
            value = float("inf")
        solution.objectives[0] = value
        return solution

    def get_name(self) -> str:
        return self._name


class _BinaryBenchmark(BinaryProblem):
    def __init__(
        self,
        name: str,
        number_of_bits: int,
        evaluator: Callable[[list[bool]], float],
        block_size: int | None = None,
    ):
        super().__init__()
        self._name = name
        self.number_of_bits = int(number_of_bits)
        if block_size and self.number_of_bits % block_size != 0:
            raise ValueError(f"{name} bit count must be divisible by {block_size}")
        self.number_of_variables = 1
        self.number_of_objectives = 1
        self.number_of_constraints = 0
        self.number_of_bits_per_variable = [self.number_of_bits]
        self.obj_directions = [self.MINIMIZE]
        self.obj_labels = ["f(x)"]
        self._evaluator = evaluator

    def evaluate(self, solution: BinarySolution) -> BinarySolution:
        solution.objectives[0] = float(self._evaluator(solution.variables[0]))
        return solution

    def create_solution(self) -> BinarySolution:
        solution = BinarySolution(number_of_variables=1, number_of_objectives=1)
        solution.variables[0] = [
            bool(random.getrandbits(1)) for _ in range(self.number_of_bits)
        ]
        return solution

    def get_name(self) -> str:
        return self._name


def _expand_bounds(value, dimension: int) -> list[float]:
    if isinstance(value, (list, tuple)):
        if len(value) != dimension:
            raise ValueError("Bound list length must match problem dimension")
        return [float(item) for item in value]
    return [float(value) for _ in range(dimension)]


@lru_cache(maxsize=None)
def _shift(seed: int, dimension: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.uniform(-80.0, 80.0, int(dimension))


@lru_cache(maxsize=None)
def _rotation(seed: int, dimension: int) -> np.ndarray:
    dimension = int(dimension)
    if dimension <= 1:
        return np.eye(dimension)
    rng = np.random.default_rng(seed)
    matrix = rng.normal(size=(dimension, dimension))
    q, r = np.linalg.qr(matrix)
    signs = np.sign(np.diag(r))
    signs[signs == 0] = 1
    return q * signs


@lru_cache(maxsize=None)
def _permutation(seed: int, dimension: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.permutation(int(dimension))


def _as_float(value: float) -> float:
    if isinstance(value, np.generic):
        return float(value)
    return value


def _elliptic(x: np.ndarray) -> float:
    dimension = len(x)
    if dimension <= 1:
        return float(np.sum(x * x))
    weights = np.power(1.0e6, np.arange(dimension) / (dimension - 1))
    return float(np.sum(weights * x * x))


def _bent_cigar(x: np.ndarray) -> float:
    return float(x[0] ** 2 + 1.0e6 * np.sum(x[1:] * x[1:]))


def _discus(x: np.ndarray) -> float:
    return float(1.0e6 * x[0] ** 2 + np.sum(x[1:] * x[1:]))


def _rosenbrock(x: np.ndarray) -> float:
    if len(x) <= 1:
        return float((1.0 - x[0]) ** 2)
    left = x[:-1]
    right = x[1:]
    return float(np.sum(100.0 * (right - left * left) ** 2 + (1.0 - left) ** 2))


def _ackley(x: np.ndarray) -> float:
    dimension = len(x)
    return float(
        -20.0 * math.exp(-0.2 * math.sqrt(float(np.sum(x * x)) / dimension))
        - math.exp(float(np.sum(np.cos(2.0 * math.pi * x))) / dimension)
        + 20.0
        + math.e
    )


def _weierstrass(x: np.ndarray) -> float:
    a = 0.5
    b = 3.0
    k_max = 20
    total = 0.0
    correction = 0.0
    for k in range(k_max + 1):
        ak = a**k
        bk = b**k
        total += float(np.sum(ak * np.cos(2.0 * math.pi * bk * (x + 0.5))))
        correction += ak * math.cos(2.0 * math.pi * bk * 0.5)
    return total - len(x) * correction


def _griewank(x: np.ndarray) -> float:
    indices = np.arange(1, len(x) + 1, dtype=float)
    return float(np.sum(x * x) / 4000.0 - np.prod(np.cos(x / np.sqrt(indices))) + 1.0)


def _rastrigin(x: np.ndarray) -> float:
    return float(np.sum(x * x - 10.0 * np.cos(2.0 * math.pi * x) + 10.0))


def _modified_schwefel(x: np.ndarray) -> float:
    dimension = len(x)
    z = x + 420.9687462275036
    result = 0.0
    for zi in z:
        if abs(zi) <= 500.0:
            gi = zi * math.sin(math.sqrt(abs(zi)))
        elif zi > 500.0:
            wrapped = 500.0 - (zi % 500.0)
            gi = (
                wrapped * math.sin(math.sqrt(abs(wrapped)))
                - ((zi - 500.0) ** 2) / (10000.0 * dimension)
            )
        else:
            wrapped = (abs(zi) % 500.0) - 500.0
            gi = (
                wrapped * math.sin(math.sqrt(abs(wrapped)))
                - ((zi + 500.0) ** 2) / (10000.0 * dimension)
            )
        result += gi
    return float(418.9829 * dimension - result)


def _katsuura(x: np.ndarray) -> float:
    dimension = len(x)
    product = 1.0
    for i, value in enumerate(x, start=1):
        inner = 0.0
        for j in range(1, 33):
            power = 2.0**j
            inner += abs(power * value - round(power * value)) / power
        product *= (1.0 + i * inner) ** (10.0 / (dimension**1.2))
    return float((10.0 / (dimension * dimension)) * product - (10.0 / (dimension * dimension)))


def _happycat(x: np.ndarray) -> float:
    dimension = len(x)
    sum_sq = float(np.sum(x * x))
    sum_x = float(np.sum(x))
    return abs(sum_sq - dimension) ** 0.25 + (0.5 * sum_sq + sum_x) / dimension + 0.5


def _hgbat(x: np.ndarray) -> float:
    dimension = len(x)
    sum_sq = float(np.sum(x * x))
    sum_x = float(np.sum(x))
    return abs(sum_sq * sum_sq - sum_x * sum_x) ** 0.5 + (
        0.5 * sum_sq + sum_x
    ) / dimension + 0.5


def _expanded_griewank_rosenbrock(x: np.ndarray) -> float:
    total = 0.0
    for i in range(len(x)):
        left = x[i]
        right = x[(i + 1) % len(x)]
        y = 100.0 * (left * left - right) ** 2 + (left - 1.0) ** 2
        total += (y * y) / 4000.0 - math.cos(y) + 1.0
    return total


def _schaffer_pair(x: float, y: float) -> float:
    radius_sq = x * x + y * y
    return 0.5 + (math.sin(math.sqrt(radius_sq)) ** 2 - 0.5) / (
        (1.0 + 0.001 * radius_sq) ** 2
    )


def _expanded_schaffer_f6(x: np.ndarray) -> float:
    return float(sum(_schaffer_pair(x[i], x[(i + 1) % len(x)]) for i in range(len(x))))


_BASIC_FUNCTIONS: dict[int, Callable[[np.ndarray], float]] = {
    1: _elliptic,
    2: _bent_cigar,
    3: _discus,
    4: _rosenbrock,
    5: _ackley,
    6: _weierstrass,
    7: _griewank,
    8: _rastrigin,
    9: _modified_schwefel,
    10: _katsuura,
    11: _happycat,
    12: _hgbat,
    13: _expanded_griewank_rosenbrock,
    14: _expanded_schaffer_f6,
}


def _rotate(seed: int, x: np.ndarray) -> np.ndarray:
    return _rotation(seed, len(x)).dot(x)


def _cec_shift(fid: int, dimension: int) -> np.ndarray:
    return _shift(2014000 + fid, dimension)


def _cec_rotation_seed(fid: int) -> int:
    return 2014500 + fid


def _cec_simple_prime(fid: int, x: np.ndarray, shift: np.ndarray, rotation_seed: int) -> float:
    if fid == 1:
        return _elliptic(_rotate(rotation_seed, x - shift))
    if fid == 2:
        return _bent_cigar(_rotate(rotation_seed, x - shift))
    if fid == 3:
        return _discus(_rotate(rotation_seed, x - shift))
    if fid == 4:
        return _rosenbrock(_rotate(rotation_seed, 2.048 * (x - shift) / 100.0) + 1.0)
    if fid == 5:
        return _ackley(_rotate(rotation_seed, x - shift))
    if fid == 6:
        return _weierstrass(_rotate(rotation_seed, 0.5 * (x - shift) / 100.0))
    if fid == 7:
        return _griewank(_rotate(rotation_seed, 600.0 * (x - shift) / 100.0))
    if fid == 8:
        return _rastrigin(5.12 * (x - shift) / 100.0)
    if fid == 9:
        return _rastrigin(_rotate(rotation_seed, 5.12 * (x - shift) / 100.0))
    if fid == 10:
        return _modified_schwefel(1000.0 * (x - shift) / 100.0)
    if fid == 11:
        return _modified_schwefel(_rotate(rotation_seed, 1000.0 * (x - shift) / 100.0))
    if fid == 12:
        return _katsuura(_rotate(rotation_seed, 5.0 * (x - shift) / 100.0))
    if fid == 13:
        return _happycat(_rotate(rotation_seed, 5.0 * (x - shift) / 100.0))
    if fid == 14:
        return _hgbat(_rotate(rotation_seed, 5.0 * (x - shift) / 100.0))
    if fid == 15:
        return _expanded_griewank_rosenbrock(
            _rotate(rotation_seed, 5.0 * (x - shift) / 100.0) + 1.0
        )
    if fid == 16:
        return _expanded_schaffer_f6(_rotate(rotation_seed, x - shift) + 1.0)
    raise ValueError(f"Unsupported CEC simple function id: {fid}")


_HYBRID_SPECS = {
    17: ([0.3, 0.3, 0.4], [9, 8, 1]),
    18: ([0.3, 0.3, 0.4], [2, 12, 8]),
    19: ([0.2, 0.2, 0.3, 0.3], [7, 6, 4, 14]),
    20: ([0.2, 0.2, 0.3, 0.3], [12, 3, 13, 8]),
    21: ([0.1, 0.2, 0.2, 0.2, 0.3], [14, 12, 4, 9, 1]),
    22: ([0.1, 0.2, 0.2, 0.2, 0.3], [10, 11, 13, 9, 5]),
}


def _split_sizes(dimension: int, percentages: list[float]) -> list[int]:
    sizes = [int(math.ceil(percent * dimension)) for percent in percentages[:-1]]
    sizes.append(dimension - sum(sizes))
    return sizes


def _hybrid_value(fid: int, x: np.ndarray, seed_offset: int = 0) -> float:
    percentages, basic_ids = _HYBRID_SPECS[fid]
    y = x - _shift(2014700 + fid + seed_offset, len(x))
    permutation = _permutation(2014800 + fid + seed_offset, len(x))
    y = y[permutation]
    sizes = _split_sizes(len(x), percentages)
    total = 0.0
    start = 0
    for component_index, (size, basic_id) in enumerate(zip(sizes, basic_ids), start=1):
        if size <= 0:
            continue
        component = y[start : start + size]
        start += size
        rotated = _rotate(2014900 + 100 * fid + 10 * seed_offset + component_index, component)
        total += _BASIC_FUNCTIONS[basic_id](rotated)
    return total


_COMPOSITION_SPECS = {
    23: {
        "sigma": [10, 20, 30, 40, 50],
        "lambda": [1, 1.0e-6, 1.0e-26, 1.0e-6, 1.0e-6],
        "bias": [0, 100, 200, 300, 400],
        "components": [4, 1, 2, 3, 1],
    },
    24: {
        "sigma": [20, 20, 20],
        "lambda": [1, 1, 1],
        "bias": [0, 100, 200],
        "components": [10, 9, 14],
    },
    25: {
        "sigma": [10, 30, 50],
        "lambda": [0.25, 1, 1.0e-7],
        "bias": [0, 100, 200],
        "components": [11, 9, 1],
    },
    26: {
        "sigma": [10, 10, 10, 10, 10],
        "lambda": [0.25, 1, 1.0e-7, 2.5, 10],
        "bias": [0, 100, 200, 300, 400],
        "components": [11, 13, 1, 6, 7],
    },
    27: {
        "sigma": [10, 10, 10, 20, 20],
        "lambda": [10, 10, 2.5, 25, 1.0e-6],
        "bias": [0, 100, 200, 300, 400],
        "components": [14, 9, 11, 6, 1],
    },
    28: {
        "sigma": [10, 20, 30, 40, 50],
        "lambda": [2.5, 10, 2.5, 5.0e-4, 1.0e-6],
        "bias": [0, 100, 200, 300, 400],
        "components": [15, 13, 11, 16, 1],
    },
    29: {
        "sigma": [10, 30, 50],
        "lambda": [1, 1, 1],
        "bias": [0, 100, 200],
        "components": [17, 18, 19],
    },
    30: {
        "sigma": [10, 30, 50],
        "lambda": [1, 1, 1],
        "bias": [0, 100, 200],
        "components": [20, 21, 22],
    },
}


def _composition_component_value(parent_fid: int, component_index: int, component_fid: int, x: np.ndarray) -> float:
    seed_offset = parent_fid * 100 + component_index
    if component_fid <= 16:
        shift = _shift(2015000 + seed_offset, len(x))
        rotation_seed = 2015100 + seed_offset
        return _cec_simple_prime(component_fid, x, shift, rotation_seed)
    return _hybrid_value(component_fid, x, seed_offset=seed_offset)


def _composition_value(fid: int, x: np.ndarray) -> float:
    spec = _COMPOSITION_SPECS[fid]
    shifts = [
        _shift(2015200 + fid * 100 + index, len(x))
        for index in range(len(spec["components"]))
    ]
    raw_weights = []
    for shift, sigma in zip(shifts, spec["sigma"]):
        distance_sq = float(np.sum((x - shift) ** 2))
        distance = math.sqrt(distance_sq)
        if distance == 0.0:
            raw_weights.append(float("inf"))
        else:
            raw_weights.append(
                (1.0 / distance) * math.exp(-distance_sq / (2.0 * len(x) * sigma * sigma))
            )

    if any(math.isinf(weight) for weight in raw_weights):
        weights = [1.0 if math.isinf(weight) else 0.0 for weight in raw_weights]
    else:
        total_weight = sum(raw_weights)
        if total_weight == 0.0:
            weights = [1.0 / len(raw_weights) for _ in raw_weights]
        else:
            weights = [weight / total_weight for weight in raw_weights]

    total = 0.0
    for index, (component_fid, weight, lambd, bias) in enumerate(
        zip(spec["components"], weights, spec["lambda"], spec["bias"]), start=1
    ):
        component_value = _composition_component_value(fid, index, component_fid, x)
        total += weight * (lambd * component_value + bias)
    return total


def _cec2014_value(fid: int, x: np.ndarray) -> float:
    if 1 <= fid <= 16:
        return _cec_simple_prime(fid, x, _cec_shift(fid, len(x)), _cec_rotation_seed(fid)) + 100.0 * fid
    if 17 <= fid <= 22:
        return _hybrid_value(fid, x) + 100.0 * fid
    if 23 <= fid <= 30:
        return _composition_value(fid, x) + 100.0 * fid
    raise ValueError(f"Unsupported CEC2014 function id: {fid}")


def _langermann(x: np.ndarray) -> float:
    c = [1.0, 2.0, 5.0, 2.0, 3.0]
    base_a = [
        [3.0, 5.0],
        [5.0, 2.0],
        [2.0, 1.0],
        [1.0, 4.0],
        [7.0, 9.0],
    ]
    total = 0.0
    for i in range(5):
        center = np.array(
            [
                base_a[i][j] if j < 2 else float((i + 2 * j + 3) % 10)
                for j in range(len(x))
            ]
        )
        distance_sq = float(np.sum((x - center) ** 2))
        total += c[i] * math.exp(-distance_sq / math.pi) * math.cos(math.pi * distance_sq)
    return -total


def _michalewicz(x: np.ndarray, m: int = 10) -> float:
    total = 0.0
    for i, value in enumerate(x, start=1):
        total += math.sin(value) * (math.sin(i * value * value / math.pi) ** (2 * m))
    return -total


def _branin(x: np.ndarray) -> float:
    x1, x2 = float(x[0]), float(x[1])
    a = 1.0
    b = 5.1 / (4.0 * math.pi * math.pi)
    c = 5.0 / math.pi
    d = 6.0
    e = 10.0
    f = 1.0 / (8.0 * math.pi)
    return a * (x2 - b * x1 * x1 + c * x1 - d) ** 2 + e * (1.0 - f) * math.cos(x1) + e


def _easom(x: np.ndarray) -> float:
    x1, x2 = float(x[0]), float(x[1])
    return -math.cos(x1) * math.cos(x2) * math.exp(-((x1 - math.pi) ** 2 + (x2 - math.pi) ** 2))


def _goldstein_price(x: np.ndarray) -> float:
    x1, x2 = float(x[0]), float(x[1])
    left = 1.0 + (x1 + x2 + 1.0) ** 2 * (
        19.0 - 14.0 * x1 + 3.0 * x1 * x1 - 14.0 * x2 + 6.0 * x1 * x2 + 3.0 * x2 * x2
    )
    right = 30.0 + (2.0 * x1 - 3.0 * x2) ** 2 * (
        18.0
        - 32.0 * x1
        + 12.0 * x1 * x1
        + 48.0 * x2
        - 36.0 * x1 * x2
        + 27.0 * x2 * x2
    )
    return left * right


def _six_hump_camel(x: np.ndarray) -> float:
    x1, x2 = float(x[0]), float(x[1])
    return (
        (4.0 - 2.1 * x1 * x1 + (x1**4) / 3.0) * x1 * x1
        + x1 * x2
        + (-4.0 + 4.0 * x2 * x2) * x2 * x2
    )


def _geatbx_value(gid: int, x: np.ndarray) -> float:
    if gid == 1:
        return float(np.sum(x * x))
    if gid == 2:
        weights = np.arange(1, len(x) + 1, dtype=float)
        return float(np.sum(weights * x * x))
    if gid == 3:
        return float(sum(np.sum(x[:i]) ** 2 for i in range(1, len(x) + 1)))
    if gid == 4:
        weights = 5.0 * np.arange(1, len(x) + 1, dtype=float)
        return float(np.sum(weights * x * x))
    if gid == 5:
        return _rosenbrock(x)
    if gid == 6:
        return _rastrigin(x)
    if gid == 7:
        return float(np.sum(-x * np.sin(np.sqrt(np.abs(x)))))
    if gid == 8:
        return _griewank(x)
    if gid == 9:
        return float(sum(abs(value) ** (index + 2) for index, value in enumerate(x)))
    if gid == 10:
        return _ackley(x)
    if gid == 11:
        return _langermann(x)
    if gid == 12:
        return _michalewicz(x)
    if gid == 13:
        return _branin(x)
    if gid == 14:
        return _easom(x)
    if gid == 15:
        return _goldstein_price(x)
    if gid == 16:
        return _six_hump_camel(x)
    raise ValueError(f"Unsupported GEATbx function id: {gid}")


_GEATBX_BOUNDS = {
    1: (-5.12, 5.12),
    2: (-5.12, 5.12),
    3: (-65.536, 65.536),
    4: (-5.12, 5.12),
    5: (-2.048, 2.048),
    6: (-5.12, 5.12),
    7: (-500.0, 500.0),
    8: (-600.0, 600.0),
    9: (-1.0, 1.0),
    10: (-32.768, 32.768),
    11: (0.0, 10.0),
    12: (0.0, math.pi),
    13: ([-5.0, 0.0], [10.0, 15.0]),
    14: (-100.0, 100.0),
    15: (-2.0, 2.0),
    16: ([-3.0, -2.0], [3.0, 2.0]),
}


def _labs(bits: list[bool]) -> float:
    energy = 0
    for distance in range(1, len(bits)):
        autocorrelation = 0
        for index in range(len(bits) - distance):
            left = 1 if bits[index] else -1
            right = 1 if bits[index + distance] else -1
            autocorrelation += left * right
        energy += autocorrelation * autocorrelation
    merit = len(bits) * len(bits) / (2.0 * energy) if energy else float("inf")
    return -merit


def _trap(bits: list[bool], block_size: int) -> float:
    score = 0
    for offset in range(0, len(bits), block_size):
        ones = sum(1 for bit in bits[offset : offset + block_size] if bit)
        score += block_size if ones == block_size else block_size - 1 - ones
    return -score


@lru_cache(maxsize=None)
def _nk_tables(number_of_bits: int, k: int, seed: int = 20260511) -> tuple[tuple[float, ...], ...]:
    rng = random.Random(seed)
    table_width = 2 ** (k + 1)
    return tuple(
        tuple(rng.random() for _ in range(table_width))
        for _ in range(number_of_bits)
    )


def _nk(bits: list[bool], k: int = 4) -> float:
    tables = _nk_tables(len(bits), k)
    fitness = 0.0
    for start in range(len(bits)):
        pattern = 0
        for shift in range(k + 1):
            bit_index = (start + shift) % len(bits)
            pattern = (pattern << 1) | int(bool(bits[bit_index]))
        fitness += tables[start][pattern]
    return -(fitness / len(bits))


def _leading_ones(bits: list[bool]) -> float:
    score = 0
    for bit in bits:
        if bit:
            score += 1
        else:
            break
    return -score


def _alternating_bits(bits: list[bool]) -> float:
    score_a = sum(1 for index, bit in enumerate(bits) if bit == (index % 2 == 0))
    score_b = len(bits) - score_a
    return -max(score_a, score_b)


def _royal_road(bits: list[bool], block_size: int = 4) -> float:
    score = 0
    for offset in range(0, len(bits), block_size):
        block = bits[offset : offset + block_size]
        if len(block) == block_size and all(block):
            score += block_size
    return -score


def _maxcut_ring(bits: list[bool]) -> float:
    cut_edges = 0
    for index, bit in enumerate(bits):
        if bit != bits[(index + 1) % len(bits)]:
            cut_edges += 1
    return -cut_edges


_CEC_DESCRIPTIONS = {
    1: "Rotated High Conditioned Elliptic Function",
    2: "Rotated Bent Cigar Function",
    3: "Rotated Discus Function",
    4: "Shifted and Rotated Rosenbrock's Function",
    5: "Shifted and Rotated Ackley's Function",
    6: "Shifted and Rotated Weierstrass Function",
    7: "Shifted and Rotated Griewank's Function",
    8: "Shifted Rastrigin's Function",
    9: "Shifted and Rotated Rastrigin's Function",
    10: "Shifted Schwefel's Function",
    11: "Shifted and Rotated Schwefel's Function",
    12: "Shifted and Rotated Katsuura Function",
    13: "Shifted and Rotated HappyCat Function",
    14: "Shifted and Rotated HGBat Function",
    15: "Shifted and Rotated Expanded Griewank plus Rosenbrock Function",
    16: "Shifted and Rotated Expanded Scaffer F6 Function",
    17: "Hybrid Function 1",
    18: "Hybrid Function 2",
    19: "Hybrid Function 3",
    20: "Hybrid Function 4",
    21: "Hybrid Function 5",
    22: "Hybrid Function 6",
    23: "Composition Function 1",
    24: "Composition Function 2",
    25: "Composition Function 3",
    26: "Composition Function 4",
    27: "Composition Function 5",
    28: "Composition Function 6",
    29: "Composition Function 7",
    30: "Composition Function 8",
}

_DISCRETE_FACTORIES: dict[str, Callable[[int], BinaryProblem]] = {
    "d01_labs_binary": lambda n: _BinaryBenchmark("d01_labs_binary", n, _labs),
    "d02_trap5": lambda n: _BinaryBenchmark("d02_trap5", n, lambda bits: _trap(bits, 5), block_size=5),
    "d03_nk_k4": lambda n: _BinaryBenchmark("d03_nk_k4", n, _nk),
    "d04_onemax": lambda n: _BinaryBenchmark("d04_onemax", n, lambda bits: -sum(1 for bit in bits if bit)),
    "d05_zeromax": lambda n: _BinaryBenchmark("d05_zeromax", n, lambda bits: -sum(1 for bit in bits if not bit)),
    "d06_leading_ones": lambda n: _BinaryBenchmark("d06_leading_ones", n, _leading_ones),
    "d07_alternating_bits": lambda n: _BinaryBenchmark("d07_alternating_bits", n, _alternating_bits),
    "d08_trap4": lambda n: _BinaryBenchmark("d08_trap4", n, lambda bits: _trap(bits, 4), block_size=4),
    "d09_royal_road4": lambda n: _BinaryBenchmark("d09_royal_road4", n, _royal_road, block_size=4),
    "d10_maxcut_ring": lambda n: _BinaryBenchmark("d10_maxcut_ring", n, _maxcut_ring),
}


def _geatbx_bounds(gid: int, number_of_variables: int):
    lower, upper = _GEATBX_BOUNDS[gid]
    if isinstance(lower, list):
        if number_of_variables <= len(lower):
            return lower[:number_of_variables], upper[:number_of_variables]
        lower = lower + [lower[-1]] * (number_of_variables - len(lower))
        upper = upper + [upper[-1]] * (number_of_variables - len(upper))
    return lower, upper


def _make_geatbx_problem(gid: int, name: str, number_of_variables: int):
    lower, upper = _geatbx_bounds(gid, number_of_variables)
    return _FloatBenchmark(
        name,
        number_of_variables,
        lower,
        upper,
        lambda x, gid=gid: _geatbx_value(gid, x),
    )


def benchmark_info() -> dict[str, BenchmarkInfo]:
    infos = {}
    for index, name in enumerate(CONTINUOUS_40_BENCHMARKS, start=1):
        infos[name] = BenchmarkInfo(
            name=name,
            kind="continuous",
            source="Definitions_of_CEC2014_benchmark_suite_Part_A.md",
            description=_CEC_DESCRIPTIONS[index],
        )
    discrete_descriptions = {
        "d01_labs_binary": "Low autocorrelation binary sequence",
        "d02_trap5": "Deceptive trap with block size 5",
        "d03_nk_k4": "Adjacent NK landscape with K=4",
        "d04_onemax": "OneMax",
        "d05_zeromax": "ZeroMax",
        "d06_leading_ones": "Leading Ones",
        "d07_alternating_bits": "Alternating bit string",
        "d08_trap4": "Deceptive trap with block size 4",
        "d09_royal_road4": "Royal Road with block size 4",
        "d10_maxcut_ring": "Max-Cut on a ring graph",
    }
    for name in DISCRETE_40_BENCHMARKS:
        infos[name] = BenchmarkInfo(
            name=name,
            kind="discrete",
            source="local binary benchmark suite",
            description=discrete_descriptions[name],
        )
    geatbx_descriptions = {
        "g01_sphere": "GEATbx De Jong function 1 / sphere model",
        "g02_axis_ellipsoid": "GEATbx axis parallel hyper-ellipsoid",
        "g03_rotated_ellipsoid": "GEATbx rotated hyper-ellipsoid / Schwefel 1.2",
        "g04_moved_ellipsoid": "GEATbx moved axis parallel hyper-ellipsoid",
        "g05_rosenbrock": "GEATbx Rosenbrock valley",
        "g06_rastrigin": "GEATbx Rastrigin function 6",
        "g07_schwefel": "GEATbx Schwefel function 7",
        "g08_griewank": "GEATbx Griewangk function 8",
        "g09_sum_power": "GEATbx sum of different power function 9",
        "g10_ackley": "GEATbx Ackley's Path function 10",
        "g11_langermann": "GEATbx Langermann function 11",
        "g12_michalewicz": "GEATbx Michalewicz function 12",
        "g13_branin": "GEATbx Branin rcos function",
        "g14_easom": "GEATbx Easom function",
        "g15_goldstein_price": "GEATbx Goldstein-Price function",
        "g16_six_hump_camel": "GEATbx six-hump camel back function",
    }
    for name in GEATBX_OPTIONAL_BENCHMARKS:
        infos[name] = BenchmarkInfo(
            name=name,
            kind="continuous_optional",
            source="some_more_benchmarks.md",
            description=geatbx_descriptions[name],
        )
    return infos


def is_registered_problem(problem_name: str) -> bool:
    return normalize_problem_name(problem_name) in _problem_factories()


def create_problem(problem_name: str, number_of_variables: int):
    normalized = normalize_problem_name(problem_name)
    factories = _problem_factories()
    if normalized not in factories:
        raise KeyError(problem_name)
    return factories[normalized](int(number_of_variables))


@lru_cache(maxsize=1)
def _problem_factories() -> dict[str, Callable[[int], object]]:
    factories: dict[str, Callable[[int], object]] = {}
    for fid, name in enumerate(CONTINUOUS_40_BENCHMARKS, start=1):
        factories[name] = (
            lambda number_of_variables, fid=fid, name=name: _FloatBenchmark(
                name,
                number_of_variables,
                -100.0,
                100.0,
                lambda x, fid=fid: _cec2014_value(fid, x),
            )
        )
        factories[f"cec2014_f{fid:02d}"] = factories[name]
        factories[f"cec_f{fid:02d}"] = factories[name]

    for gid, name in enumerate(GEATBX_OPTIONAL_BENCHMARKS, start=1):
        factories[name] = (
            lambda number_of_variables, gid=gid, name=name: _make_geatbx_problem(
                gid, name, number_of_variables
            )
        )
        factories[f"geatbx_{gid:02d}"] = factories[name]

    factories.update(_DISCRETE_FACTORIES)
    factories.update(
        {
            "onemax": factories["d04_onemax"],
            "zeromax": factories["d05_zeromax"],
            "leading_ones": factories["d06_leading_ones"],
            "alternating_bits": factories["d07_alternating_bits"],
            "trap4": factories["d08_trap4"],
            "royal_road4": factories["d09_royal_road4"],
            "maxcut_ring": factories["d10_maxcut_ring"],
            "objfun1": factories["g01_sphere"],
            "objfun1a": factories["g02_axis_ellipsoid"],
            "objfun1b": factories["g03_rotated_ellipsoid"],
            "objfun1c": factories["g04_moved_ellipsoid"],
            "objfun2": factories["g05_rosenbrock"],
            "objfun6": factories["g06_rastrigin"],
            "objfun7": factories["g07_schwefel"],
            "objfun8": factories["g08_griewank"],
            "objfun9": factories["g09_sum_power"],
            "objfun10": factories["g10_ackley"],
            "objfun11": factories["g11_langermann"],
            "objfun12": factories["g12_michalewicz"],
            "objbran": factories["g13_branin"],
            "objeaso": factories["g14_easom"],
            "objgold": factories["g15_goldstein_price"],
            "objsixh": factories["g16_six_hump_camel"],
        }
    )
    return factories
