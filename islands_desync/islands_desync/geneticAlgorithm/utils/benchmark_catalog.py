from dataclasses import dataclass


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

_DISCRETE_DESCRIPTIONS = {
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

_GEATBX_DESCRIPTIONS = {
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


def benchmark_info() -> dict[str, BenchmarkInfo]:
    infos = {}
    for index, name in enumerate(CONTINUOUS_40_BENCHMARKS, start=1):
        infos[name] = BenchmarkInfo(
            name=name,
            kind="continuous",
            source="Definitions_of_CEC2014_benchmark_suite_Part_A.md",
            description=_CEC_DESCRIPTIONS[index],
        )
    for name in DISCRETE_40_BENCHMARKS:
        infos[name] = BenchmarkInfo(
            name=name,
            kind="discrete",
            source="local binary benchmark suite",
            description=_DISCRETE_DESCRIPTIONS[name],
        )
    for name in GEATBX_OPTIONAL_BENCHMARKS:
        infos[name] = BenchmarkInfo(
            name=name,
            kind="continuous_optional",
            source="some_more_benchmarks.md",
            description=_GEATBX_DESCRIPTIONS[name],
        )
    return infos
