"""Shared asynchronous request batcher for the Athena GPU island runner.

The module can be imported without Ray.  ``make_actor_class`` imports Ray only
when the real runner constructs actors, which keeps the request contract unit
testable on a laptop without the cluster environment.
"""
from __future__ import annotations

import asyncio
from collections import Counter
import gzip
import json
from pathlib import Path
import time

import numpy as np


PHASES = {"initial", "offspring"}


def validate_request(request: dict, vectors, *, max_rows: int) -> tuple[dict, np.ndarray]:
    if not isinstance(request, dict):
        raise ValueError("evaluation request must be a dictionary")
    required = {
        "schema_version",
        "request_id",
        "run_id",
        "island_id",
        "shard_id",
        "phase",
        "step",
        "evaluations_before",
        "problem_id",
        "dimension",
        "instance_seed",
        "rows",
        "row_context",
    }
    missing = sorted(required - set(request))
    if missing:
        raise ValueError(f"evaluation request is missing fields: {missing}")
    if request["schema_version"] != 1:
        raise ValueError("unsupported evaluation request schema")
    if not isinstance(request["request_id"], str) or not request["request_id"]:
        raise ValueError("request_id must be a non-empty string")
    if request["phase"] not in PHASES:
        raise ValueError("phase must be initial or offspring")
    for name in (
        "island_id",
        "shard_id",
        "step",
        "evaluations_before",
        "dimension",
        "instance_seed",
        "rows",
    ):
        value = request[name]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{name} must be a nonnegative integer")
    if request["dimension"] < 1 or request["rows"] < 1:
        raise ValueError("dimension and rows must be positive")
    if request["rows"] > max_rows:
        raise ValueError("one request cannot exceed max_rows")
    if not isinstance(request["problem_id"], str) or not request["problem_id"].strip():
        raise ValueError("problem_id must be a non-empty string")
    if not isinstance(request["row_context"], list) or len(request["row_context"]) != request["rows"]:
        raise ValueError("row_context length must equal rows")
    if hasattr(vectors, "__cuda_array_interface__"):
        raise ValueError("batcher accepts host arrays only")
    values = np.asarray(vectors)
    if values.ndim != 2 or values.shape != (request["rows"], request["dimension"]):
        raise ValueError("vectors shape does not match request rows/dimension")
    if values.dtype.kind not in "biuf" or not np.all(np.isfinite(values)):
        raise ValueError("vectors must contain finite numeric host values")
    normalized = dict(request)
    normalized["problem_id"] = request["problem_id"].strip().lower()
    normalized["dtype"] = str(values.dtype)
    return normalized, np.ascontiguousarray(values)


def request_group_key(request: dict) -> tuple:
    """Do not mix phases or benchmark instances in a backend call."""
    return (
        request["phase"],
        request["problem_id"],
        request["dimension"],
        request["instance_seed"],
        request["dtype"],
    )


def _json_safe(value):
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    return value


def _write_json(path: Path, value) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(_json_safe(value), indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _write_jsonl_gzip(path: Path, records) -> None:
    temporary = path.with_name(path.name + ".tmp")
    with gzip.open(temporary, "wt", encoding="utf-8", compresslevel=6) as output:
        for record in records:
            output.write(json.dumps(_json_safe(record), separators=(",", ":"), allow_nan=False))
            output.write("\n")
    temporary.replace(path)


def make_actor_class():
    import ray

    @ray.remote(
        num_cpus=1,
        max_concurrency=512,
        max_restarts=0,
        max_task_retries=0,
    )
    class EvaluationBatcher:
        def __init__(
            self,
            gpu_evaluator,
            *,
            initial_target_rows: int,
            steady_target_rows: int,
            max_rows: int,
            initial_max_wait_ms: float,
            steady_max_wait_ms: float,
        ):
            self.gpu_evaluator = gpu_evaluator
            self.targets = {
                "initial": int(initial_target_rows),
                "offspring": int(steady_target_rows),
            }
            self.wait_seconds = {
                "initial": float(initial_max_wait_ms) / 1000.0,
                "offspring": float(steady_max_wait_ms) / 1000.0,
            }
            self.max_rows = int(max_rows)
            if min(self.targets.values()) < 1 or max(self.targets.values()) > self.max_rows:
                raise ValueError("invalid batch targets")
            if min(self.wait_seconds.values()) <= 0:
                raise ValueError("batch wait limits must be positive")
            self.pending = {}
            self.pending_rows = Counter()
            self.timers = {}
            self.dispatch_tasks = {}
            self.seen_request_ids = set()
            self.request_records = []
            self.batch_records = []
            self.batch_sequence = 0
            self.response_count = 0
            self.error_count = 0
            self.maximum_pending_rows = 0
            self.maximum_pending_requests = 0

        def _ensure_timer(self, key):
            if not self.pending.get(key) or key in self.timers:
                return
            oldest = self.pending[key][0]["enqueued_monotonic"]
            delay = max(0.0, oldest + self.wait_seconds[key[0]] - time.monotonic())
            task = asyncio.create_task(self._timeout(key, delay))
            self.timers[key] = task

        async def _timeout(self, key, delay):
            try:
                await asyncio.sleep(delay)
                self.timers.pop(key, None)
                # A request can become overdue while the preceding GPU call is
                # still completing.  The active dispatch owns the key until
                # its done callback runs; that callback will re-arm this
                # overdue queue after removing the old task.
                if key in self.dispatch_tasks:
                    return
                self._spawn_dispatch(key, "timeout")
            except asyncio.CancelledError:
                return

        def _spawn_dispatch(self, key, reason):
            if key in self.dispatch_tasks:
                return
            task = asyncio.create_task(self._dispatch(key, reason))
            self.dispatch_tasks[key] = task

            def finished(completed):
                if self.dispatch_tasks.get(key) is completed:
                    self.dispatch_tasks.pop(key, None)
                if not self.pending.get(key):
                    return
                if self.pending_rows[key] >= self.targets[key[0]]:
                    self._spawn_dispatch(key, "size")
                else:
                    self._ensure_timer(key)

            task.add_done_callback(finished)

        def _take_batch(self, key):
            selected = []
            rows = 0
            queue = self.pending.get(key, [])
            while queue and rows + queue[0]["vectors"].shape[0] <= self.max_rows:
                entry = queue.pop(0)
                selected.append(entry)
                rows += entry["vectors"].shape[0]
            self.pending_rows[key] -= rows
            if not queue:
                self.pending.pop(key, None)
                self.pending_rows.pop(key, None)
            return selected, rows

        async def _dispatch(self, key, reason):
            first_dispatch = True
            while self.pending.get(key):
                target = self.targets[key[0]]
                if not first_dispatch and self.pending_rows[key] < target:
                    break
                if reason == "size" and first_dispatch and self.pending_rows[key] < target:
                    break
                first_dispatch = False
                timer = self.timers.pop(key, None)
                if timer is not None and timer is not asyncio.current_task():
                    timer.cancel()
                entries, rows = self._take_batch(key)
                if not entries:
                    raise RuntimeError("batcher could not make progress")
                self.batch_sequence += 1
                batch_id = f"gpu-batch-{self.batch_sequence}"
                dispatch_unix = time.time()
                dispatch_monotonic = time.monotonic()
                vectors = np.concatenate([entry["vectors"] for entry in entries], axis=0)
                batch_record = {
                    "schema_version": 1,
                    "batch_id": batch_id,
                    "phase": key[0],
                    "problem_id": key[1],
                    "dimension": key[2],
                    "instance_seed": key[3],
                    "dtype": key[4],
                    "dispatch_reason": reason,
                    "request_count": len(entries),
                    "row_count": rows,
                    "unique_islands": len({entry["request"]["island_id"] for entry in entries}),
                    "dispatch_timestamp_unix": dispatch_unix,
                    "oldest_request_wait_seconds": dispatch_monotonic
                    - min(entry["enqueued_monotonic"] for entry in entries),
                }
                try:
                    gpu_result = await self.gpu_evaluator.evaluate.remote(
                        key[1], vectors, instance_seed=key[3]
                    )
                    values = np.asarray(gpu_result["values"], dtype=np.float64)
                    if values.shape != (rows,) or not np.all(np.isfinite(values)):
                        raise FloatingPointError("GPU evaluator returned invalid objectives")
                    completed_unix = time.time()
                    completed_monotonic = time.monotonic()
                    batch_record.update(
                        {
                            "status": "complete",
                            "completed_timestamp_unix": completed_unix,
                            "batcher_wall_seconds": completed_monotonic - dispatch_monotonic,
                            "gpu_profile": gpu_result["profile"],
                        }
                    )
                    offset = 0
                    for entry in entries:
                        count = entry["vectors"].shape[0]
                        result = values[offset : offset + count].copy()
                        offset += count
                        record = entry["record"]
                        record.update(
                            {
                                "status": "complete",
                                "batch_id": batch_id,
                                "dispatch_reason": reason,
                                "dispatch_timestamp_unix": dispatch_unix,
                                "completed_timestamp_unix": completed_unix,
                                "queue_wait_seconds": dispatch_monotonic
                                - entry["enqueued_monotonic"],
                                "roundtrip_inside_batcher_seconds": completed_monotonic
                                - entry["enqueued_monotonic"],
                            }
                        )
                        self.response_count += 1
                        if not entry["future"].done():
                            entry["future"].set_result(
                                {
                                    "schema_version": 1,
                                    "request_id": entry["request"]["request_id"],
                                    "batch_id": batch_id,
                                    "values": result,
                                }
                            )
                except BaseException as error:
                    self.error_count += len(entries)
                    failed_unix = time.time()
                    batch_record.update(
                        {
                            "status": "failed",
                            "failed_timestamp_unix": failed_unix,
                            "error": repr(error),
                        }
                    )
                    for entry in entries:
                        entry["record"].update(
                            {
                                "status": "failed",
                                "batch_id": batch_id,
                                "error": repr(error),
                                "failed_timestamp_unix": failed_unix,
                            }
                        )
                        if not entry["future"].done():
                            entry["future"].set_exception(
                                RuntimeError(f"GPU batch {batch_id} failed: {error!r}")
                            )
                finally:
                    self.batch_records.append(batch_record)
                reason = "size"
            self._ensure_timer(key)

        async def evaluate(self, request, vectors):
            request, values = validate_request(request, vectors, max_rows=self.max_rows)
            request_id = request["request_id"]
            if request_id in self.seen_request_ids:
                raise ValueError(f"duplicate evaluation request_id: {request_id}")
            self.seen_request_ids.add(request_id)
            loop = asyncio.get_running_loop()
            future = loop.create_future()
            enqueued_unix = time.time()
            enqueued_monotonic = time.monotonic()
            record = {
                **request,
                "enqueued_timestamp_unix": enqueued_unix,
                "status": "pending",
            }
            self.request_records.append(record)
            key = request_group_key(request)
            self.pending.setdefault(key, []).append(
                {
                    "request": request,
                    "vectors": values,
                    "future": future,
                    "record": record,
                    "enqueued_monotonic": enqueued_monotonic,
                }
            )
            self.pending_rows[key] += values.shape[0]
            self.maximum_pending_rows = max(self.maximum_pending_rows, sum(self.pending_rows.values()))
            self.maximum_pending_requests = max(
                self.maximum_pending_requests,
                sum(len(entries) for entries in self.pending.values()),
            )
            if self.pending_rows[key] >= self.targets[request["phase"]]:
                self._spawn_dispatch(key, "size")
            else:
                self._ensure_timer(key)
            return await future

        async def flush(self):
            while self.pending or self.dispatch_tasks:
                for key in list(self.pending):
                    self._spawn_dispatch(key, "flush")
                tasks = list(self.dispatch_tasks.values())
                if tasks:
                    await asyncio.gather(*tasks)
                else:
                    await asyncio.sleep(0)
            return self.summary()

        def summary(self):
            phase_requests = Counter(record["phase"] for record in self.request_records)
            phase_rows = Counter()
            for record in self.request_records:
                phase_rows[record["phase"]] += record["rows"]
            completed_batches = [
                record
                for record in self.batch_records
                if record.get("status") == "complete"
            ]
            batches_by_reason = Counter(
                record.get("dispatch_reason") for record in completed_batches
            )
            completed_count = len(completed_batches)
            completed_requests = sum(
                record["request_count"] for record in completed_batches
            )
            completed_rows = sum(record["row_count"] for record in completed_batches)
            small_batches = sum(
                record["request_count"] <= 3 for record in completed_batches
            )
            return {
                "schema_version": 1,
                "request_count": len(self.request_records),
                "response_count": self.response_count,
                "error_count": self.error_count,
                "batch_count": len(self.batch_records),
                "row_count": sum(record["rows"] for record in self.request_records),
                "requests_by_phase": dict(phase_requests),
                "rows_by_phase": dict(phase_rows),
                "maximum_pending_rows": self.maximum_pending_rows,
                "maximum_pending_requests": self.maximum_pending_requests,
                "batch_quality": {
                    "completed_batches_by_reason": dict(batches_by_reason),
                    "average_requests_per_completed_batch": (
                        completed_requests / completed_count if completed_count else 0.0
                    ),
                    "average_rows_per_completed_batch": (
                        completed_rows / completed_count if completed_count else 0.0
                    ),
                    "batches_with_at_most_three_requests": small_batches,
                    "fraction_with_at_most_three_requests": (
                        small_batches / completed_count if completed_count else 0.0
                    ),
                },
                "policy": {
                    "initial_target_rows": self.targets["initial"],
                    "steady_target_rows": self.targets["offspring"],
                    "max_rows": self.max_rows,
                    "initial_max_wait_ms": self.wait_seconds["initial"] * 1000.0,
                    "steady_max_wait_ms": self.wait_seconds["offspring"] * 1000.0,
                },
            }

        def export_metrics(self, directory):
            path = Path(directory)
            path.mkdir(parents=True, exist_ok=True)
            _write_jsonl_gzip(path / "evaluation_requests.jsonl.gz", self.request_records)
            _write_jsonl_gzip(path / "gpu_batches.jsonl.gz", self.batch_records)
            summary = self.summary()
            _write_json(path / "summary.json", summary)
            return summary

    return EvaluationBatcher
