"""Problem selection/configuration shared by the HPC builder and preflight."""
import json
import hashlib
import os
from pathlib import Path

from jmetal.problem.singleobjective.unconstrained import Rastrigin, Sphere

from islands_desync.geneticAlgorithm.utils import benchmarks_refined


CONFIG_PATH = Path(__file__).resolve().parents[1] / "algorithm/configurations/algorithm_configuration.json"
ENV_FIELDS = {
    "ISLANDS_NUMBER_OF_VARIABLES": "number_of_variables",
    "ISLANDS_NUMBER_OF_EVALUATIONS": "number_of_evaluations",
    "ISLANDS_POPULATION_SIZE": "population_size",
    "ISLANDS_OFFSPRING_POPULATION_SIZE": "offspring_population_size",
}


def runtime_sha256():
    """Identify the main runtime, including migration/operators, across nodes."""
    root = Path(__file__).resolve().parents[2]
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*.py"), key=lambda p: p.relative_to(root).as_posix()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8") + b"\0")
        digest.update(path.read_bytes().replace(b"\r\n", b"\n") + b"\0")
    return digest.hexdigest()


def create_problem(name, dimension):
    name = name.strip().lower()
    if benchmarks_refined.is_registered_problem(name):
        return benchmarks_refined.create_problem(name, dimension)
    if name in ("sphere", "sphe"):
        return Sphere(dimension)
    if name in ("rastrigin", "rast"):
        return Rastrigin(dimension)
    raise ValueError(f"Unknown problem {name!r}; use sphere, rastrigin or a name from benchmarks_refined --list")


def load_configuration():
    path = Path(os.environ.get("ISLANDS_CONFIG", str(CONFIG_PATH)))
    configuration = json.loads(path.read_text(encoding="utf-8"))
    for env, field in ENV_FIELDS.items():
        value = os.environ.get(env, configuration[field])
        if isinstance(value, bool) or isinstance(value, float):
            raise ValueError(f"{field} must be a positive integer")
        configuration[field] = int(value)
        if configuration[field] <= 0:
            raise ValueError(f"{field} must be positive")
    population = configuration["population_size"]
    offspring = configuration["offspring_population_size"]
    evaluations = configuration["number_of_evaluations"]
    if population < 2 or offspring % 2:
        raise ValueError("Two-parent crossover requires population >= 2 and an even offspring count")
    if evaluations <= population or (evaluations - population) % offspring:
        raise ValueError("Evaluation budget must be population + a positive integer number of offspring batches")
    for field in ("how_many_data_intervals", "plot_population_interval"):
        if configuration[field] <= 0:
            raise ValueError(f"{field} must be positive")
    configuration["problem"] = os.environ.get("ISLANDS_PROBLEM", configuration.get("problem", "sphere")).strip().lower()
    return configuration


def operator_metadata(algorithm):
    result = {}
    for label, operator in (("mutation", algorithm.mutation_operator),
                            ("crossover", algorithm.crossover_operator),
                            ("selection", algorithm.selection_operator)):
        values = {"class": type(operator).__name__}
        for field in ("probability", "perturbation", "distribution_index"):
            if hasattr(operator, field):
                values[field] = getattr(operator, field)
        result[label] = values
    return result
