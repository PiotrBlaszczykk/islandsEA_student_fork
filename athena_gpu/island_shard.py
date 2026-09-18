"""Ray actor hosting several independent logical IslandsEA algorithms."""
from __future__ import annotations

import random

import numpy as np


def rotated_order(values, cursor):
    """Return one cyclic ordering without mutating the recorded shard order."""
    values = tuple(values)
    if not values:
        return values
    start = int(cursor) % len(values)
    return values[start:] + values[:start]


def bounded_lead_eligible(
    island_ids,
    steps_by_island,
    pending_islands,
    *,
    maximum_completed_step_lead,
):
    """Select runnable islands while preventing a physical-shard runaway.

    A lead of two still permits steps 0/1/2 to coexist, so this is bounded
    asynchronous execution rather than a shard or global generation barrier.
    """
    active = tuple(int(value) for value in island_ids)
    if not active:
        return set()
    if maximum_completed_step_lead < 1:
        raise ValueError("maximum_completed_step_lead must be positive")
    minimum_step = min(int(steps_by_island[island]) for island in active)
    pending = set(pending_islands)
    return {
        island
        for island in active
        if island not in pending
        and int(steps_by_island[island])
        < minimum_step + maximum_completed_step_lead
    }


def execute_with_rng_states(python_state, numpy_state, callback):
    """Execute one logical-island phase without leaking module RNG state."""
    outer_python = random.getstate()
    outer_numpy = np.random.get_state()
    random.setstate(python_state)
    np.random.set_state(numpy_state)
    try:
        result = callback()
        return result, random.getstate(), np.random.get_state()
    finally:
        random.setstate(outer_python)
        np.random.set_state(outer_numpy)


def make_actor_class():
    import ray

    @ray.remote(num_cpus=1, max_restarts=0, max_task_retries=0)
    class IslandShard:
        def __init__(
            self,
            *,
            shard_id,
            island_ids,
            adjacency,
            run_params,
            run_id,
            problem_id,
            dimension,
            instance_seed,
            batcher,
            router,
            package_root,
            operation_timeout_seconds,
            scheduler_max_step_lead,
        ):
            import os
            import random
            import socket
            import time

            import numpy as np

            self.os = os
            self.random = random
            self.np = np
            self.time = time
            self.shard_id = int(shard_id)
            self.island_ids = tuple(int(value) for value in island_ids)
            if not self.island_ids:
                raise ValueError("IslandShard cannot be empty")
            self.adjacency = {int(key): list(value) for key, value in adjacency.items()}
            if any(island not in self.adjacency for island in self.island_ids):
                raise ValueError("shard adjacency is incomplete")
            self.run_params = dict(run_params)
            self.run_id = str(run_id)
            self.problem_id = str(problem_id).strip().lower()
            self.dimension = int(dimension)
            self.instance_seed = int(instance_seed)
            self.batcher = batcher
            self.router = router
            self.package_root = str(package_root)
            self.operation_timeout_seconds = float(operation_timeout_seconds)
            self.scheduler_max_step_lead = int(scheduler_max_step_lead)
            if self.scheduler_max_step_lead < 1:
                raise ValueError("scheduler_max_step_lead must be positive")
            self.shard_position = {
                island_id: position
                for position, island_id in enumerate(self.island_ids)
            }
            self.submission_cursor = 0
            self.completion_cursor = 0
            self.scheduler_sweeps = 0
            self.maximum_observed_step_lead = 0
            self.hostname = socket.gethostname()
            self.pid = os.getpid()
            self.ray_node_id = str(ray.get_runtime_context().get_node_id())
            self.constructed_timestamp_unix = time.time()
            self.states = {}
            self.initialized = False
            self.run_finished = False
            self.finish_barrier_end = None
            self.delivery_barrier_end = None
            os.chdir(self.package_root)

        def _execute_with_island_rng(self, state, callback):
            result, python_state, numpy_state = execute_with_rng_states(
                state["python_rng_state"],
                state["numpy_rng_state"],
                callback,
            )
            state["python_rng_state"] = python_state
            state["numpy_rng_state"] = numpy_state
            return result

        def _prepare_algorithm(self, island_id):
            if island_id in self.states:
                return self.states[island_id]["algorithm"].path
            if island_id not in self.island_ids:
                raise ValueError(f"island {island_id} is not assigned to shard {self.shard_id}")
            from islands_desync.geneticAlgorithm.run_hpc.create_algorithm_hpc import (
                create_algorithm_hpc,
            )
            from islands_desync.geneticAlgorithm.run_hpc.run_algorithm_params import (
                RunAlgorithmParams,
            )
            from athena_gpu.migration_router import ShardedMigration

            migration = ShardedMigration(
                island_id,
                self.adjacency[island_id],
                self.router,
                timeout_seconds=self.operation_timeout_seconds,
            )
            outer_python = self.random.getstate()
            outer_numpy = self.np.random.get_state()
            try:
                algorithm = create_algorithm_hpc(
                    island_id,
                    migration,
                    RunAlgorithmParams(**self.run_params),
                )
                python_state = self.random.getstate()
                numpy_state = self.np.random.get_state()
            finally:
                self.random.setstate(outer_python)
                self.np.random.set_state(outer_numpy)
            self.states[island_id] = {
                "algorithm": algorithm,
                "migration": migration,
                "python_rng_state": python_state,
                "numpy_rng_state": numpy_state,
                "request_sequence": 0,
                "done": False,
                "algorithm_start_timestamp_unix": None,
                "algorithm_compute_end_timestamp_unix": None,
            }
            return algorithm.path

        def prepare_island_zero(self):
            if 0 not in self.island_ids:
                raise RuntimeError("prepare_island_zero called on a shard without island 0")
            path = self._prepare_algorithm(0)
            algorithm = self.states[0]["algorithm"]
            metadata = (
                algorithm.problem.benchmark_metadata()
                if hasattr(algorithm.problem, "benchmark_metadata")
                else {"name": algorithm.problem.get_name()}
            )
            return {
                "shard_id": self.shard_id,
                "island": 0,
                "run_directory": path,
                "benchmark": metadata,
                "active_operators": algorithm.active_operators,
            }

        def prepare_remaining(self):
            prepared = []
            for island_id in self.island_ids:
                self._prepare_algorithm(island_id)
                prepared.append(island_id)
            return {
                "shard_id": self.shard_id,
                "islands": prepared,
                "scheduler_order": list(self.island_ids),
                "scheduler": {
                    "algorithm": "rotating-round-robin-bounded-lead-v1",
                    "maximum_completed_step_lead_within_shard": self.scheduler_max_step_lead,
                },
                "hostname": self.hostname,
                "pid": self.pid,
                "ray_node_id": self.ray_node_id,
            }

        @staticmethod
        def _solution_vectors(solutions):
            from islands_desync.geneticAlgorithm.utils.decision_variables import (
                decision_variables,
            )

            return [list(decision_variables(solution)) for solution in solutions]

        def _vectors(self, solutions):
            dtype = self.np.int64 if self.problem_id.startswith("b") else self.np.float64
            values = self.np.asarray(self._solution_vectors(solutions), dtype=dtype)
            if values.shape != (len(solutions), self.dimension):
                raise RuntimeError(
                    f"unexpected solution matrix shape {values.shape}; "
                    f"expected {(len(solutions), self.dimension)}"
                )
            return self.np.ascontiguousarray(values)

        @staticmethod
        def _assign_objectives(solutions, values):
            if len(solutions) != len(values):
                raise RuntimeError("GPU result length differs from solution count")
            for solution, value in zip(solutions, values):
                solution.objectives[0] = float(value)
            return solutions

        def _request(self, island_id, state, phase, solutions, evaluations_before):
            state["request_sequence"] += 1
            algorithm = state["algorithm"]
            rows = len(solutions)
            request_id = f"{self.run_id}:{island_id}:{state['request_sequence']}"
            request = {
                "schema_version": 1,
                "request_id": request_id,
                "run_id": self.run_id,
                "island_id": island_id,
                "shard_id": self.shard_id,
                "phase": phase,
                "step": 0 if phase == "initial" else algorithm.step_num,
                "evaluations_before": int(evaluations_before),
                "problem_id": self.problem_id,
                "dimension": self.dimension,
                "instance_seed": self.instance_seed,
                "rows": rows,
                "row_context": [
                    {
                        "index": index,
                        "logical_evaluation": int(evaluations_before) + index,
                    }
                    for index in range(rows)
                ],
            }
            return request, self._vectors(solutions)

        def _resolve_evaluation(self, ref, expected_request_id, solutions):
            response = ray.get(ref, timeout=self.operation_timeout_seconds)
            if response.get("request_id") != expected_request_id:
                raise RuntimeError("evaluation response request_id mismatch")
            values = self.np.asarray(response.get("values"), dtype=self.np.float64)
            if values.shape != (len(solutions),) or not self.np.all(self.np.isfinite(values)):
                raise RuntimeError("evaluation response has invalid objectives")
            return self._assign_objectives(solutions, values), response["batch_id"]

        def initialize(self):
            if set(self.states) != set(self.island_ids):
                raise RuntimeError("all shard algorithms must be prepared before initialization")
            if self.initialized:
                raise RuntimeError("shard initialized twice")
            pending = {}
            for island_id in self.island_ids:
                state = self.states[island_id]
                algorithm = state["algorithm"]
                started = self.time.time()
                state["algorithm_start_timestamp_unix"] = started
                algorithm.start_computing_time = started

                def create_initial():
                    algorithm.solutions = algorithm.create_initial_solutions()
                    return algorithm.solutions

                solutions = self._execute_with_island_rng(state, create_initial)
                request, vectors = self._request(island_id, state, "initial", solutions, 0)
                ref = self.batcher.evaluate.remote(request, vectors)
                pending[ref] = (island_id, request["request_id"], solutions)

            while pending:
                ready, _ = ray.wait(
                    list(pending),
                    num_returns=1,
                    timeout=self.operation_timeout_seconds,
                )
                if not ready:
                    raise TimeoutError(f"shard {self.shard_id} initial evaluation timed out")
                for ref in ready:
                    island_id, request_id, solutions = pending.pop(ref)
                    state = self.states[island_id]
                    algorithm = state["algorithm"]
                    evaluated, _ = self._resolve_evaluation(ref, request_id, solutions)

                    def finish_initial():
                        algorithm.solutions = evaluated
                        algorithm.init_progress()

                    self._execute_with_island_rng(state, finish_initial)
            self.initialized = True
            return {
                "shard_id": self.shard_id,
                "initialized_islands": list(self.island_ids),
            }

        def _island_zero_can_advance(self):
            state = self.states.get(0)
            if state is None or state["done"]:
                return True
            algorithm = state["algorithm"]
            if algorithm.step_num + 1 < algorithm.last_step:
                return True
            return all(
                other["done"]
                for island_id, other in self.states.items()
                if island_id != 0
            )

        def run(self):
            if not self.initialized:
                raise RuntimeError("initialize the shard before run")
            if self.run_finished:
                raise RuntimeError("shard run called twice")
            pending = {}
            while not all(state["done"] for state in self.states.values()):
                pending_islands = {value[0] for value in pending.values()}
                blocked = set()
                if 0 in self.states and not self._island_zero_can_advance():
                    blocked.add(0)
                schedulable = [
                    island_id
                    for island_id in self.island_ids
                    if not self.states[island_id]["done"] and island_id not in blocked
                ]
                eligible = bounded_lead_eligible(
                    schedulable,
                    {
                        island_id: self.states[island_id]["algorithm"].step_num
                        for island_id in schedulable
                    },
                    pending_islands,
                    maximum_completed_step_lead=self.scheduler_max_step_lead,
                )
                submitted = 0
                for island_id in rotated_order(self.island_ids, self.submission_cursor):
                    state = self.states[island_id]
                    if island_id not in eligible:
                        continue
                    algorithm = state["algorithm"]
                    evaluations_before = algorithm.evaluations
                    offspring = self._execute_with_island_rng(
                        state,
                        algorithm.prepare_step_for_evaluation,
                    )
                    request, vectors = self._request(
                        island_id,
                        state,
                        "offspring",
                        offspring,
                        evaluations_before,
                    )
                    ref = self.batcher.evaluate.remote(request, vectors)
                    pending[ref] = (island_id, request["request_id"], offspring)
                    submitted += 1

                if submitted:
                    # Moving the start by one (rather than by the number of
                    # submissions) prevents a complete sweep from restoring
                    # the same permanent first/last position on every step.
                    self.submission_cursor = (
                        self.submission_cursor + 1
                    ) % len(self.island_ids)
                    self.scheduler_sweeps += 1

                if not pending:
                    unfinished = [
                        island_id
                        for island_id, state in self.states.items()
                        if not state["done"]
                    ]
                    raise RuntimeError(f"shard scheduler stalled with unfinished islands {unfinished}")
                ready, _ = ray.wait(
                    list(pending),
                    num_returns=1,
                    timeout=self.operation_timeout_seconds,
                )
                if not ready:
                    raise TimeoutError(f"shard {self.shard_id} evaluation timed out")
                remaining = [ref for ref in pending if ref not in ready]
                if remaining:
                    additional, _ = ray.wait(
                        remaining,
                        num_returns=len(remaining),
                        timeout=0,
                    )
                    ready.extend(additional)
                completion_rank = {
                    island_id: rank
                    for rank, island_id in enumerate(
                        rotated_order(self.island_ids, self.completion_cursor)
                    )
                }
                ready.sort(key=lambda ref: completion_rank[pending[ref][0]])
                if ready:
                    self.completion_cursor = (
                        self.completion_cursor + 1
                    ) % len(self.island_ids)
                for ref in ready:
                    island_id, request_id, offspring = pending.pop(ref)
                    state = self.states[island_id]
                    algorithm = state["algorithm"]
                    evaluated, _ = self._resolve_evaluation(ref, request_id, offspring)

                    def complete_step():
                        algorithm.complete_step_after_evaluation(evaluated)
                        algorithm.update_progress()

                    self._execute_with_island_rng(state, complete_step)
                    stopping = algorithm.stopping_condition_is_met
                    if stopping() if callable(stopping) else bool(stopping):
                        state["done"] = True
                        state["algorithm_compute_end_timestamp_unix"] = self.time.time()
                        algorithm.total_computing_time = (
                            state["algorithm_compute_end_timestamp_unix"]
                            - state["algorithm_start_timestamp_unix"]
                        )
                active_steps = [
                    state["algorithm"].step_num
                    for state in self.states.values()
                    if not state["done"]
                ]
                if active_steps:
                    self.maximum_observed_step_lead = max(
                        self.maximum_observed_step_lead,
                        max(active_steps) - min(active_steps),
                    )
            for state in self.states.values():
                state["migration"].acknowledge_finish()
            self.run_finished = True
            return {
                "shard_id": self.shard_id,
                "completed_islands": list(self.island_ids),
                "request_counts": {
                    str(island_id): state["request_sequence"]
                    for island_id, state in self.states.items()
                },
                "scheduler": {
                    "algorithm": "rotating-round-robin-bounded-lead-v1",
                    "maximum_completed_step_lead_within_shard": self.scheduler_max_step_lead,
                    "maximum_observed_step_lead": self.maximum_observed_step_lead,
                    "sweeps": self.scheduler_sweeps,
                },
            }

        def acknowledge_deliveries(self):
            if not self.run_finished:
                raise RuntimeError("run must finish before delivery acknowledgement")
            # All shard ``run`` calls have returned before the driver invokes
            # this method, so this is the same explicit finish-barrier boundary
            # recorded by the historical one-actor-per-island path.
            self.finish_barrier_end = self.time.time()
            refs = [
                state["migration"].acknowledge_outgoing()
                for state in self.states.values()
            ]
            ray.get(refs, timeout=self.operation_timeout_seconds)
            ray.get(
                self.router.wait_for_delivery.remote(self.operation_timeout_seconds),
                timeout=self.operation_timeout_seconds + 5.0,
            )
            self.delivery_barrier_end = self.time.time()
            return {"shard_id": self.shard_id, "delivery_acknowledged": list(self.island_ids)}

        def finalize(self):
            if self.finish_barrier_end is None or self.delivery_barrier_end is None:
                raise RuntimeError("delivery barrier must finish before metrics export")
            results = []
            for island_id in self.island_ids:
                state = self.states[island_id]
                algorithm = state["algorithm"]
                migration = state["migration"]
                metrics_export_start = self.time.time()
                migration_telemetry, queue_metrics = migration.finalize_metrics()
                runtime_metrics = {
                    "schema_version": 1,
                    "island": island_id,
                    "hostname": self.hostname,
                    "pid": self.pid,
                    "ray_node_id": self.ray_node_id,
                    "physical_actor_kind": "IslandShard",
                    "shard_id": self.shard_id,
                    "shard_island_ids": list(self.island_ids),
                    "shard_position": self.shard_position[island_id],
                    "scheduler_algorithm": "rotating-round-robin-bounded-lead-v1",
                    "scheduler_maximum_completed_step_lead": self.scheduler_max_step_lead,
                    "scheduler_maximum_observed_step_lead": self.maximum_observed_step_lead,
                    "constructed_timestamp_unix": self.constructed_timestamp_unix,
                    "algorithm_start_timestamp_unix": state["algorithm_start_timestamp_unix"],
                    "algorithm_compute_end_timestamp_unix": state["algorithm_compute_end_timestamp_unix"],
                    "finish_barrier_end_timestamp_unix": self.finish_barrier_end,
                    "delivery_barrier_end_timestamp_unix": self.delivery_barrier_end,
                    "algorithm_wall_seconds": state["algorithm_compute_end_timestamp_unix"]
                    - state["algorithm_start_timestamp_unix"],
                    "finish_barrier_wait_seconds": self.finish_barrier_end
                    - state["algorithm_compute_end_timestamp_unix"],
                    "delivery_ack_and_barrier_seconds": self.delivery_barrier_end
                    - self.finish_barrier_end,
                    "migration_measurement_start_timestamp_unix": migration.start,
                    "migration_measurement_end_timestamp_unix": migration.end,
                    "actual_evaluations": algorithm.evaluations,
                    "actual_steps": algorithm.step_num,
                    "evaluation_request_count": state["request_sequence"],
                    "queue": queue_metrics,
                }
                algorithm.export_research_metrics(
                    migration_telemetry=migration_telemetry,
                    runtime_metrics=runtime_metrics,
                )
                metrics_export_end = self.time.time()
                runtime_metrics.update(
                    {
                        "metrics_export_start_timestamp_unix": metrics_export_start,
                        "metrics_export_end_timestamp_unix": metrics_export_end,
                        "metrics_export_wall_seconds": metrics_export_end - metrics_export_start,
                    }
                )
                algorithm.write_runtime_metrics(runtime_metrics)
                result = algorithm.get_result()
                run_time = migration.run_time()
                results.append(
                    {
                        "island": island_id,
                        "iterations": algorithm.step_num,
                        "time": run_time,
                        "ips": algorithm.step_num / run_time,
                        "start": migration.start,
                        "end": migration.end,
                        "evaluations": algorithm.evaluations,
                        "final_fitness": float(result.objectives[0]),
                        "hostname": self.hostname,
                        "pid": self.pid,
                        "ray_node_id": self.ray_node_id,
                        "physical_actor_kind": "IslandShard",
                        "shard_id": self.shard_id,
                        "shard_position": self.shard_position[island_id],
                        "sent_migrant_count": len(migration_telemetry["sent_events"]),
                        "processed_migrant_count": len(algorithm.processed_migration_events),
                        "prefetched_unprocessed_migrant_count": len(
                            migration_telemetry["prefetched_unprocessed_events"]
                        ),
                        "queued_unprocessed_migrant_count": len(
                            migration_telemetry["queued_unprocessed_events"]
                        ),
                        "queue_depth_at_end": queue_metrics["queue_depth_at_query"],
                        "metrics_export_time": metrics_export_end - metrics_export_start,
                        "evaluation_request_count": state["request_sequence"],
                    }
                )
            return results

        def placement(self):
            return {
                "shard_id": self.shard_id,
                "island_ids": list(self.island_ids),
                "hostname": self.hostname,
                "pid": self.pid,
                "ray_node_id": self.ray_node_id,
                "scheduler": {
                    "algorithm": "rotating-round-robin-bounded-lead-v1",
                    "maximum_completed_step_lead_within_shard": self.scheduler_max_step_lead,
                },
            }

    return IslandShard
