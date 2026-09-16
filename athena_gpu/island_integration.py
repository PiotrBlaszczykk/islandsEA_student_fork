#!/usr/bin/env python3
"""Validate and print the resource/scientific plan for Athena island sharding.

This module is deliberately side-effect free: it does not import Ray or CuPy,
does not create result directories and cannot submit a SLURM job.  It turns the
integration design into a machine-checkable contract before actors are added.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json


BACKEND_MAX_BATCH_ROWS = 8192
FULL_PROFILE_ISLANDS = 200
FULL_PROFILE_SHARDS = 12
SLURM_CPUS = 16
RAY_CPUS = 15


def _positive_int(name: str, value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


def balanced_shard_plan(islands: int, shards: int) -> tuple[tuple[int, ...], ...]:
    """Return stable contiguous island IDs, balanced by at most one island."""
    islands = _positive_int("islands", islands)
    shards = _positive_int("shards", shards)
    if shards > islands:
        raise ValueError("shards cannot exceed logical islands")
    base, extra = divmod(islands, shards)
    result = []
    next_island = 0
    for shard_id in range(shards):
        size = base + int(shard_id < extra)
        result.append(tuple(range(next_island, next_island + size)))
        next_island += size
    if next_island != islands:
        raise AssertionError("internal shard accounting error")
    return tuple(result)


@dataclass(frozen=True)
class ResourcePlan:
    slurm_cpus: int = SLURM_CPUS
    ray_cpus: int = RAY_CPUS
    driver_cpus: int = 1
    gpu_evaluators: int = 1
    gpu_evaluator_cpus_each: int = 1
    evaluation_batchers: int = 1
    evaluation_batcher_cpus_each: int = 1
    migration_routers: int = 1
    migration_router_cpus_each: int = 1
    island_shards: int = FULL_PROFILE_SHARDS
    island_shard_cpus_each: int = 1
    gpus: int = 1
    ray_heap_gib: int = 96
    object_store_gib: int = 8

    @property
    def actor_cpus(self) -> int:
        return (
            self.gpu_evaluators * self.gpu_evaluator_cpus_each
            + self.evaluation_batchers * self.evaluation_batcher_cpus_each
            + self.migration_routers * self.migration_router_cpus_each
            + self.island_shards * self.island_shard_cpus_each
        )

    def validate(self) -> None:
        for name, value in asdict(self).items():
            _positive_int(name, value)
        if self.gpus != 1 or self.gpu_evaluators != 1:
            raise ValueError("the first Athena integration profile requires one GPU/evaluator")
        if self.ray_cpus + self.driver_cpus > self.slurm_cpus:
            raise ValueError("Ray plus driver CPU reservations exceed the SLURM allocation")
        if self.actor_cpus > self.ray_cpus:
            raise ValueError("actor CPU reservations exceed advertised Ray CPUs")


@dataclass(frozen=True)
class BatchPolicy:
    initial_target_rows: int = 3200
    steady_target_rows: int = 800
    max_rows: int = 3200
    initial_max_wait_ms: float = 50.0
    steady_max_wait_ms: float = 2.0
    max_pending_per_island: int = 1
    backend_max_rows: int = BACKEND_MAX_BATCH_ROWS

    def validate(self) -> None:
        _positive_int("initial_target_rows", self.initial_target_rows)
        _positive_int("steady_target_rows", self.steady_target_rows)
        _positive_int("max_rows", self.max_rows)
        _positive_int("max_pending_per_island", self.max_pending_per_island)
        _positive_int("backend_max_rows", self.backend_max_rows)
        for name in ("initial_max_wait_ms", "steady_max_wait_ms"):
            value = getattr(self, name)
            if isinstance(value, bool) or value <= 0:
                raise ValueError(f"{name} must be positive")
        if self.initial_target_rows > self.max_rows:
            raise ValueError("initial_target_rows cannot exceed max_rows")
        if self.steady_target_rows > self.max_rows:
            raise ValueError("steady_target_rows cannot exceed max_rows")
        if self.max_rows > self.backend_max_rows:
            raise ValueError("max_rows exceeds the batch backend hard limit")
        if self.max_pending_per_island != 1:
            raise ValueError("the first integration profile allows one in-flight request per island")


@dataclass(frozen=True)
class ScientificPlan:
    logical_islands: int = FULL_PROFILE_ISLANDS
    evaluations_per_island: int = 8000
    population: int = 16
    offspring: int = 4
    migrants: int = 5
    migration_interval: int = 5
    migrant_selection: str = "best"
    migrant_acceptance: str = "plain"
    repeat: int = 1
    requested_seed: int = 20260912

    @property
    def repeat_base_seed(self) -> int:
        return self.requested_seed + (self.repeat - 1) * 1_000_000

    @property
    def total_evaluations(self) -> int:
        return self.logical_islands * self.evaluations_per_island

    @property
    def initial_rows(self) -> int:
        return self.logical_islands * self.population

    @property
    def ideal_steady_rows(self) -> int:
        return self.logical_islands * self.offspring

    def island_seed(self, island_id: int) -> int:
        if not 0 <= island_id < self.logical_islands:
            raise ValueError("island_id outside logical island range")
        return self.repeat_base_seed + island_id

    def validate(self, *, diagnostic: bool) -> None:
        for name in (
            "logical_islands", "evaluations_per_island", "population",
            "offspring", "migrants", "migration_interval", "repeat",
        ):
            _positive_int(name, getattr(self, name))
        if isinstance(self.requested_seed, bool) or not isinstance(self.requested_seed, int) or self.requested_seed < 0:
            raise ValueError("requested_seed must be a nonnegative integer")
        if not diagnostic and self.logical_islands != FULL_PROFILE_ISLANDS:
            raise ValueError("the full Athena integration profile requires exactly 200 logical islands")
        if self.population < 2 or self.offspring % 2:
            raise ValueError("two-parent crossover requires population >= 2 and even offspring")
        if self.evaluations_per_island <= self.population:
            raise ValueError("evaluation budget must exceed the initial population")
        if (self.evaluations_per_island - self.population) % self.offspring:
            raise ValueError("evaluation budget must be population plus whole offspring batches")
        if not 1 <= self.migrants <= self.population:
            raise ValueError("migrants must be between one and population size")


def build_plan(
    scientific: ScientificPlan,
    resources: ResourcePlan,
    batching: BatchPolicy,
    *,
    diagnostic: bool = False,
) -> dict:
    scientific.validate(diagnostic=diagnostic)
    resources.validate()
    batching.validate()
    if resources.island_shards > scientific.logical_islands:
        raise ValueError("island shard count exceeds logical island count")
    mapping = balanced_shard_plan(scientific.logical_islands, resources.island_shards)
    flat = tuple(island for shard in mapping for island in shard)
    if flat != tuple(range(scientific.logical_islands)):
        raise AssertionError("shard mapping must cover every island exactly once")

    return {
        "schema_version": 1,
        "profile": "athena-integration-diagnostic" if diagnostic else "athena-integration-200",
        "approved_study_profile": False,
        "submission_performed": False,
        "execution": {
            "platform": "Athena",
            "backend": "athena-cupy",
            "dtype": "float64",
            "driver_outside_ray": True,
            "physical_gpu": "one allocated A100",
            "generation_barrier": False,
            "dispatch_reasons": ["size", "timeout", "flush"],
        },
        "scientific": {
            **asdict(scientific),
            "migration_interval_unit": "evaluation-count difference",
            "metrics_profile": "research-v1-full-buffered",
            "island_seed_formula": "repeat_base + island_id",
            "repeat_base_seed": scientific.repeat_base_seed,
            "total_evaluations": scientific.total_evaluations,
            "initial_rows": scientific.initial_rows,
            "ideal_steady_rows": scientific.ideal_steady_rows,
        },
        "resources": {**asdict(resources), "actor_cpus": resources.actor_cpus},
        "batching": asdict(batching),
        "shards": [
            {"shard_id": shard_id, "island_ids": list(island_ids)}
            for shard_id, island_ids in enumerate(mapping)
        ],
        "island_to_shard": [
            next(shard_id for shard_id, island_ids in enumerate(mapping) if island_id in island_ids)
            for island_id in range(scientific.logical_islands)
        ],
        "island_seeds": [
            scientific.island_seed(island_id)
            for island_id in range(scientific.logical_islands)
        ],
        "required_gates_before_gpu_canary": [
            "RNG interleaving parity",
            "legacy step versus split-step parity",
            "migration event reconciliation",
            "evaluation request/result reconciliation",
            "local Ray NumpyBatchBackend canary",
            "clean pinned commit and explicit user submission",
        ],
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--islands", type=int, default=FULL_PROFILE_ISLANDS)
    result.add_argument("--shards", type=int, default=FULL_PROFILE_SHARDS)
    result.add_argument("--evaluations", type=int, default=8000)
    result.add_argument("--population", type=int, default=16)
    result.add_argument("--offspring", type=int, default=4)
    result.add_argument("--migrants", type=int, default=5)
    result.add_argument("--interval", type=int, default=5)
    result.add_argument("--strategy", default="best")
    result.add_argument("--acceptance", default="plain")
    result.add_argument("--repeat", type=int, default=1)
    result.add_argument("--seed", type=int, default=20260912)
    result.add_argument("--initial-target-batch-rows", type=int, default=3200)
    result.add_argument("--steady-target-batch-rows", type=int, default=800)
    result.add_argument("--max-batch-rows", type=int, default=3200)
    result.add_argument("--initial-max-wait-ms", type=float, default=50.0)
    result.add_argument("--steady-max-wait-ms", type=float, default=2.0)
    result.add_argument("--diagnostic", action="store_true")
    return result


def main() -> int:
    args = parser().parse_args()
    scientific = ScientificPlan(
        logical_islands=args.islands,
        evaluations_per_island=args.evaluations,
        population=args.population,
        offspring=args.offspring,
        migrants=args.migrants,
        migration_interval=args.interval,
        migrant_selection=args.strategy,
        migrant_acceptance=args.acceptance,
        repeat=args.repeat,
        requested_seed=args.seed,
    )
    resources = ResourcePlan(island_shards=args.shards)
    batching = BatchPolicy(
        initial_target_rows=args.initial_target_batch_rows,
        steady_target_rows=args.steady_target_batch_rows,
        max_rows=args.max_batch_rows,
        initial_max_wait_ms=args.initial_max_wait_ms,
        steady_max_wait_ms=args.steady_max_wait_ms,
    )
    print(json.dumps(build_plan(scientific, resources, batching, diagnostic=args.diagnostic), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
