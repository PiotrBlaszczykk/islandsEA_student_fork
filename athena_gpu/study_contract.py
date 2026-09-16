"""Pure, side-effect-free resource contract for the Athena GPU study runner."""
from __future__ import annotations

from dataclasses import asdict, dataclass


STUDY_ISLANDS = 144
STUDY_SHARDS = 12
SLURM_CPUS = 16
RAY_CPUS = 15
BACKEND_MAX_ROWS = 8192


def _positive_int(name: str, value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


def balanced_shards(islands: int, shards: int) -> tuple[tuple[int, ...], ...]:
    islands = _positive_int("islands", islands)
    shards = _positive_int("shards", shards)
    if shards > islands:
        raise ValueError("shards cannot exceed logical islands")
    base, extra = divmod(islands, shards)
    result = []
    first = 0
    for shard_id in range(shards):
        size = base + int(shard_id < extra)
        result.append(tuple(range(first, first + size)))
        first += size
    if tuple(island for group in result for island in group) != tuple(range(islands)):
        raise AssertionError("shard mapping must cover every island exactly once")
    return tuple(result)


@dataclass(frozen=True)
class AthenaResources:
    slurm_cpus: int = SLURM_CPUS
    ray_cpus: int = RAY_CPUS
    driver_cpus: int = 1
    island_shards: int = STUDY_SHARDS
    gpu_evaluators: int = 1
    evaluation_batchers: int = 1
    migration_routers: int = 1
    gpus: int = 1
    ray_heap_gib: int = 96
    object_store_gib: int = 8

    @property
    def actor_cpus(self) -> int:
        return (
            self.island_shards
            + self.gpu_evaluators
            + self.evaluation_batchers
            + self.migration_routers
        )

    def validate(self, *, full_study: bool) -> None:
        for name, value in asdict(self).items():
            _positive_int(name, value)
        if self.slurm_cpus != SLURM_CPUS or self.ray_cpus != RAY_CPUS:
            raise ValueError("Athena profile requires 16 physical and 15 Ray CPUs")
        if self.driver_cpus != 1 or self.gpus != 1 or self.gpu_evaluators != 1:
            raise ValueError("Athena profile requires one driver and one GPU evaluator")
        if self.ray_cpus + self.driver_cpus != self.slurm_cpus:
            raise ValueError("Ray and driver reservations must account for all 16 CPUs")
        if self.actor_cpus > self.ray_cpus:
            raise ValueError("actor CPU reservations exceed advertised Ray CPUs")
        if full_study and self.island_shards != STUDY_SHARDS:
            raise ValueError("the study profile requires exactly 12 island shards")


@dataclass(frozen=True)
class StudyBatchPolicy:
    initial_target_rows: int
    steady_target_rows: int
    max_rows: int
    initial_max_wait_ms: float = 50.0
    steady_max_wait_ms: float = 2.0
    max_pending_per_island: int = 1
    backend_max_rows: int = BACKEND_MAX_ROWS

    @classmethod
    def for_run(
        cls,
        islands: int,
        population: int,
        offspring: int,
        *,
        initial_max_wait_ms: float = 50.0,
        steady_max_wait_ms: float = 2.0,
    ) -> "StudyBatchPolicy":
        return cls(
            initial_target_rows=islands * population,
            steady_target_rows=islands * offspring,
            max_rows=islands * population,
            initial_max_wait_ms=initial_max_wait_ms,
            steady_max_wait_ms=steady_max_wait_ms,
        )

    def validate(self) -> None:
        for name in (
            "initial_target_rows",
            "steady_target_rows",
            "max_rows",
            "max_pending_per_island",
            "backend_max_rows",
        ):
            _positive_int(name, getattr(self, name))
        for name in ("initial_max_wait_ms", "steady_max_wait_ms"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
                raise ValueError(f"{name} must be positive")
        if self.initial_target_rows > self.max_rows:
            raise ValueError("initial target exceeds max_rows")
        if self.steady_target_rows > self.max_rows:
            raise ValueError("steady target exceeds max_rows")
        if self.max_rows > self.backend_max_rows:
            raise ValueError("max_rows exceeds the backend hard limit")
        if self.max_pending_per_island != 1:
            raise ValueError("only one in-flight request per island is permitted")


def build_study_plan(
    *,
    islands: int = STUDY_ISLANDS,
    shards: int = STUDY_SHARDS,
    population: int = 16,
    offspring: int = 4,
    evaluations: int = 8000,
    diagnostic: bool = False,
    initial_max_wait_ms: float = 50.0,
    steady_max_wait_ms: float = 2.0,
) -> dict:
    for name, value in (
        ("islands", islands),
        ("shards", shards),
        ("population", population),
        ("offspring", offspring),
        ("evaluations", evaluations),
    ):
        _positive_int(name, value)
    if not diagnostic and islands != STUDY_ISLANDS:
        raise ValueError("a normal study run requires exactly 144 islands")
    if population < 2 or offspring % 2:
        raise ValueError("two-parent crossover requires population >=2 and even offspring")
    if evaluations <= population or (evaluations - population) % offspring:
        raise ValueError("evaluation budget must equal population plus whole offspring batches")
    resources = AthenaResources(island_shards=shards)
    resources.validate(full_study=not diagnostic)
    batching = StudyBatchPolicy.for_run(
        islands,
        population,
        offspring,
        initial_max_wait_ms=initial_max_wait_ms,
        steady_max_wait_ms=steady_max_wait_ms,
    )
    batching.validate()
    mapping = balanced_shards(islands, shards)
    return {
        "schema_version": 1,
        "profile": "athena-study-144" if not diagnostic else "athena-study-diagnostic",
        "approved_study_profile": not diagnostic,
        "execution_backend": "athena-gpu-sharded",
        "scientific": {
            "logical_islands": islands,
            "population": population,
            "offspring": offspring,
            "evaluations_per_island": evaluations,
            "expected_steps_per_island": (evaluations - population) // offspring,
            "initial_rows": islands * population,
            "maximum_independent_steady_rows": islands * offspring,
            "generation_barrier": False,
        },
        "resources": {**asdict(resources), "actor_cpus": resources.actor_cpus},
        "batching": asdict(batching),
        "shards": [
            {"shard_id": shard_id, "island_ids": list(island_ids)}
            for shard_id, island_ids in enumerate(mapping)
        ],
    }
