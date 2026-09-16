"""Logical per-island migration queues for the sharded Athena runner."""
from __future__ import annotations

import asyncio
import copy
import random
import time


def historical_drain(queue: list) -> list:
    """Preserve the legacy list-mutation drain behaviour exactly."""
    return [queue.pop(0) for _ in queue]


def make_actor_class():
    import ray

    @ray.remote(
        num_cpus=1,
        max_concurrency=512,
        max_restarts=0,
        max_task_retries=0,
    )
    class MigrationRouter:
        def __init__(self, island_count: int):
            if isinstance(island_count, bool) or not isinstance(island_count, int) or island_count < 1:
                raise ValueError("island_count must be positive")
            self.island_count = island_count
            self.queues = [[] for _ in range(island_count)]
            self.metrics = [
                {
                    "schema_version": 1,
                    "island": island,
                    "received_total": 0,
                    "dequeued_total": 0,
                    "fetch_calls": 0,
                    "empty_fetch_calls": 0,
                    "maximum_queue_depth": 0,
                    "first_enqueue_timestamp_unix": None,
                    "last_enqueue_timestamp_unix": None,
                }
                for island in range(island_count)
            ]
            self.finished = set()
            self.delivery_complete = set()
            self.finish_event = asyncio.Event()
            self.delivery_event = asyncio.Event()

        def _island(self, island_id):
            if isinstance(island_id, bool) or not isinstance(island_id, int):
                raise ValueError("island_id must be an integer")
            if not 0 <= island_id < self.island_count:
                raise ValueError("island_id is outside the router range")
            return island_id

        def enqueue(self, destination_island: int, message: dict):
            destination_island = self._island(destination_island)
            if not isinstance(message, dict) or "solution" not in message or "event" not in message:
                raise ValueError("migration message must contain solution and event")
            timestamp = time.time()
            monotonic = time.monotonic()
            queue = self.queues[destination_island]
            event = dict(message["event"])
            event.update(
                {
                    "enqueue_timestamp_unix": timestamp,
                    "enqueue_monotonic": monotonic,
                    "destination_island": destination_island,
                    "destination_actor_kind": "MigrationRouter",
                    "queue_depth_after_enqueue": len(queue) + 1,
                }
            )
            queue.append({"solution": message["solution"], "event": event})
            metrics = self.metrics[destination_island]
            metrics["received_total"] += 1
            metrics["maximum_queue_depth"] = max(metrics["maximum_queue_depth"], len(queue))
            if metrics["first_enqueue_timestamp_unix"] is None:
                metrics["first_enqueue_timestamp_unix"] = timestamp
            metrics["last_enqueue_timestamp_unix"] = timestamp
            return {"destination_island": destination_island, "event_id": event.get("event_id")}

        def drain(self, island_id: int):
            island_id = self._island(island_id)
            timestamp = time.time()
            monotonic = time.monotonic()
            queue = self.queues[island_id]
            before = len(queue)
            messages = historical_drain(queue)
            after = len(queue)
            for position, message in enumerate(messages):
                event = dict(message["event"])
                event.update(
                    {
                        "dequeue_timestamp_unix": timestamp,
                        "dequeue_monotonic": monotonic,
                        "queue_residence_ms": max(
                            0.0,
                            (monotonic - event.get("enqueue_monotonic", monotonic)) * 1000.0,
                        ),
                        "queue_depth_before_dequeue_batch": before,
                        "queue_depth_after_dequeue_batch": after,
                        "dequeue_position_in_batch": position,
                    }
                )
                message["event"] = event
            metrics = self.metrics[island_id]
            metrics["fetch_calls"] += 1
            metrics["dequeued_total"] += len(messages)
            if not messages:
                metrics["empty_fetch_calls"] += 1
            return {
                "messages": messages,
                "fetch": {
                    "schema_version": 1,
                    "fetch_sequence": metrics["fetch_calls"],
                    "destination_island": island_id,
                    "timestamp_unix": timestamp,
                    "monotonic": monotonic,
                    "queue_depth_before": before,
                    "dequeued_count": len(messages),
                    "queue_depth_after": after,
                },
            }

        def signal_finish(self, island_id: int):
            island_id = self._island(island_id)
            if island_id in self.finished:
                raise RuntimeError(f"duplicate finish signal from island {island_id}")
            self.finished.add(island_id)
            if len(self.finished) == self.island_count:
                self.finish_event.set()
            return len(self.finished)

        async def wait_for_finish(self, timeout_seconds: float):
            await asyncio.wait_for(self.finish_event.wait(), timeout=float(timeout_seconds))
            return sorted(self.finished)

        def mark_delivery_complete(self, island_id: int):
            island_id = self._island(island_id)
            if island_id in self.delivery_complete:
                raise RuntimeError(f"duplicate delivery acknowledgement from island {island_id}")
            self.delivery_complete.add(island_id)
            if len(self.delivery_complete) == self.island_count:
                self.delivery_event.set()
            return len(self.delivery_complete)

        async def wait_for_delivery(self, timeout_seconds: float):
            await asyncio.wait_for(self.delivery_event.wait(), timeout=float(timeout_seconds))
            return sorted(self.delivery_complete)

        def runtime_metrics(self, island_id: int):
            island_id = self._island(island_id)
            remaining = []
            for message in self.queues[island_id]:
                event = copy.deepcopy(message["event"])
                event.update(
                    {
                        "record_type": "process",
                        "processed": False,
                        "process_status": "queued_not_dequeued_at_end_of_run",
                        "accepted_by_filter": None,
                        "added_to_candidates": False,
                        "survived_replacement": False,
                        "survived_h_steps": None,
                    }
                )
                remaining.append(event)
            return {
                **self.metrics[island_id],
                "queue_depth_at_query": len(self.queues[island_id]),
                "queried_timestamp_unix": time.time(),
                "remaining_event_records": remaining,
            }

        def summary(self):
            return {
                "schema_version": 1,
                "island_count": self.island_count,
                "finished_islands": sorted(self.finished),
                "delivery_complete_islands": sorted(self.delivery_complete),
                "received_total": sum(item["received_total"] for item in self.metrics),
                "dequeued_total": sum(item["dequeued_total"] for item in self.metrics),
                "queued_at_end": sum(len(queue) for queue in self.queues),
                "maximum_queue_depth": max(item["maximum_queue_depth"] for item in self.metrics),
            }

    return MigrationRouter


class ShardedMigration:
    """Migration duck type consumed by ``GeneticIslandAlgorithm``."""

    def __init__(self, island_id: int, destination_ids: list[int], router, *, timeout_seconds: float):
        import ray

        if not destination_ids:
            raise ValueError(f"island {island_id} has no migration destination")
        self.ray = ray
        self.island_id = island_id
        self.destination_ids = list(destination_ids)
        self.router = router
        self.timeout_seconds = float(timeout_seconds)
        self.start = None
        self.end = None
        self.sent_events = []
        self.queue_fetches = []
        self.send_sequence = 0
        self.latest_delivery_refs = {}
        self.finish_ref = None
        self.prefetch_ref = self.router.drain.remote(island_id)

    def start_time_measure(self):
        self.start = time.time()

    def end_time_measure(self):
        self.end = time.time()

    def run_time(self):
        if self.start is None or self.end is None:
            raise RuntimeError("migration runtime measurement is incomplete")
        return self.end - self.start

    def wait_for_all_start(self):
        # The driver invokes shard ``run`` only after every logical island has
        # completed initialization.  Blocking per-island barriers would
        # deadlock multiple logical islands hosted by one actor.
        return None

    def migrate_individuals(
        self,
        individuals_to_migrate,
        iteration_number,
        island_number,
        ind_timestamp,
        src_island,
        evaluations=None,
        source_best=None,
    ):
        batch_id = f"{src_island}:{iteration_number}"
        for batch_position, individual in enumerate(individuals_to_migrate):
            self.send_sequence += 1
            destination = random.choice(self.destination_ids)
            event = {
                "schema_version": 1,
                "event_id": f"{src_island}:{self.send_sequence}",
                "batch_id": batch_id,
                "batch_position": batch_position,
                "batch_size": len(individuals_to_migrate),
                "source_island": src_island,
                "destination_island": destination,
                "source_step": iteration_number,
                "source_evaluations": evaluations,
                "fitness_at_send": float(individual.objectives[0]),
                "source_best_at_send": source_best,
                "solution_origin_island": getattr(individual, "from_island", None),
                "solution_origin_evaluation": getattr(individual, "from_evaluation", None),
                "send_timestamp_unix": ind_timestamp,
                "send_monotonic": time.monotonic(),
                "record_type": "send",
                "dispatch_status": "submitted_to_migration_router",
            }
            delivery_ref = self.router.enqueue.remote(
                destination,
                {"solution": individual, "event": event},
            )
            self.sent_events.append(dict(event))
            self.latest_delivery_refs[destination] = delivery_ref

    @staticmethod
    def _decode(packet, step_num, evaluations):
        from islands_desync.islands.core.Migration import MigrationInfo

        messages = packet["messages"]
        fetch = dict(packet["fetch"])
        fetch.update(
            {
                "consumer_step": step_num,
                "consumer_evaluations": evaluations,
                "consumer_observed_timestamp_unix": time.time(),
            }
        )
        individuals = [message["solution"] for message in messages]
        events = [dict(message["event"]) for message in messages]
        return individuals, MigrationInfo(
            step=step_num,
            ev=evaluations,
            iteration_numbers=[event["source_step"] for event in events],
            timestamps=[event["send_timestamp_unix"] for event in events],
            src_islands=[event["source_island"] for event in events],
            fitnesses=[event["fitness_at_send"] for event in events],
            events=events,
            fetch=fetch,
        )

    def receive_individuals(self, step_num: int, evaluations: int):
        packet = self.ray.get(self.prefetch_ref)
        self.prefetch_ref = self.router.drain.remote(self.island_id)
        individuals, info = self._decode(packet, step_num, evaluations)
        self.queue_fetches.append(info.fetch)
        return individuals, info

    def signal_finish(self):
        if self.finish_ref is not None:
            raise RuntimeError(f"island {self.island_id} signalled finish twice")
        self.finish_ref = self.router.signal_finish.remote(self.island_id)

    def wait_for_finish(self):
        if self.finish_ref is not None:
            self.ray.get(self.finish_ref, timeout=self.timeout_seconds)
        self.ray.get(
            self.router.wait_for_finish.remote(self.timeout_seconds),
            timeout=self.timeout_seconds + 5.0,
        )

    def acknowledge_finish(self):
        if self.finish_ref is None:
            raise RuntimeError(f"island {self.island_id} never signalled finish")
        return self.ray.get(self.finish_ref, timeout=self.timeout_seconds)

    def acknowledge_outgoing(self):
        if self.latest_delivery_refs:
            self.ray.get(list(self.latest_delivery_refs.values()), timeout=self.timeout_seconds)
        return self.router.mark_delivery_complete.remote(self.island_id)

    def wait_for_outgoing_deliveries(self):
        raise RuntimeError("delivery barrier must be coordinated once per shard")

    def finalize_metrics(self):
        packet = self.ray.get(self.prefetch_ref, timeout=self.timeout_seconds)
        fetch = dict(packet["fetch"])
        fetch.update(
            {
                "consumer_step": None,
                "consumer_evaluations": None,
                "consumer_observed_timestamp_unix": time.time(),
                "end_of_run_prefetch": True,
            }
        )
        self.queue_fetches.append(fetch)
        prefetched = []
        for message in packet["messages"]:
            event = copy.deepcopy(message["event"])
            event.update(
                {
                    "record_type": "process",
                    "processed": False,
                    "process_status": "prefetched_not_processed_at_end_of_run",
                    "accepted_by_filter": None,
                    "added_to_candidates": False,
                    "survived_replacement": False,
                    "survived_h_steps": None,
                }
            )
            prefetched.append(event)
        queue_metrics = self.ray.get(
            self.router.runtime_metrics.remote(self.island_id),
            timeout=self.timeout_seconds,
        )
        queued = queue_metrics.pop("remaining_event_records")
        return {
            "sent_events": self.sent_events,
            "queue_fetches": self.queue_fetches,
            "prefetched_unprocessed_events": prefetched,
            "queued_unprocessed_events": queued,
        }, queue_metrics
