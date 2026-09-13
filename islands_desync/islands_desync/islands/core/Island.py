import os
import socket
import time

import ray

from islands_desync.geneticAlgorithm.run_hpc.run_algorithm_params import (
    RunAlgorithmParams,
)
from islands_desync.islands.core.Computation import Computation
from islands_desync.islands.core.SignalActor import SignalActor
from islands_desync.islands.selectAlgorithm import SelectAlgorithm


@ray.remote(num_cpus=1)
class Island:
    def __init__(self, island_id: int, select_algorithm: SelectAlgorithm):
        self.island_id: int = island_id
        self.computation = None
        self.islands: [Island] = []
        self.immigrants = []
        self.select_algorithm: SelectAlgorithm = select_algorithm
        self.hostname = socket.gethostname()
        self.pid = os.getpid()
        try:
            self.ray_node_id = str(ray.get_runtime_context().get_node_id())
        except Exception:
            self.ray_node_id = None
        self.queue_metrics = {
            "schema_version": 1,
            "island": island_id,
            "hostname": self.hostname,
            "pid": self.pid,
            "ray_node_id": self.ray_node_id,
            "received_total": 0,
            "dequeued_total": 0,
            "fetch_calls": 0,
            "empty_fetch_calls": 0,
            "maximum_queue_depth": 0,
            "first_enqueue_timestamp_unix": None,
            "last_enqueue_timestamp_unix": None,
        }

    def start(
        self,
        island_handle,
        islands: ["Island"],
        destination_island_ids: list[int],
        algorithm_params: RunAlgorithmParams,
        signal_actor: SignalActor,
    ):
        self.islands = islands
        self.computation = Computation.remote(
            island_handle,
            self.island_id,
            islands,
            destination_island_ids,
            self.select_algorithm,
            algorithm_params,
            signal_actor
        )

        return self.computation

    def receive_immigrant(self, immigrant_iteration):
        enqueue_timestamp = time.time()
        enqueue_monotonic = time.monotonic()
        if isinstance(immigrant_iteration, dict) and "event" in immigrant_iteration:
            immigrant_iteration = dict(immigrant_iteration)
            event = dict(immigrant_iteration["event"])
            event.update(
                {
                    "enqueue_timestamp_unix": enqueue_timestamp,
                    "enqueue_monotonic": enqueue_monotonic,
                    "destination_hostname": self.hostname,
                    "destination_pid": self.pid,
                    "destination_ray_node_id": self.ray_node_id,
                    "queue_depth_after_enqueue": len(self.immigrants) + 1,
                }
            )
            immigrant_iteration["event"] = event
        self.immigrants.append(immigrant_iteration)
        self.queue_metrics["received_total"] += 1
        self.queue_metrics["maximum_queue_depth"] = max(
            self.queue_metrics["maximum_queue_depth"], len(self.immigrants)
        )
        if self.queue_metrics["first_enqueue_timestamp_unix"] is None:
            self.queue_metrics["first_enqueue_timestamp_unix"] = enqueue_timestamp
        self.queue_metrics["last_enqueue_timestamp_unix"] = enqueue_timestamp

    def get_immigrants(self):
        fetch_timestamp = time.time()
        fetch_monotonic = time.monotonic()
        queue_depth_before = len(self.immigrants)

        # Preserve the historical drain semantics exactly.  This comprehension
        # mutates the list while iterating and therefore may leave messages for
        # the next fetch; queue telemetry makes that behaviour observable.
        messages = [self.immigrants.pop(0) for _ in self.immigrants]
        queue_depth_after = len(self.immigrants)
        for position, message in enumerate(messages):
            if isinstance(message, dict) and "event" in message:
                event = dict(message["event"])
                event.update(
                    {
                        "dequeue_timestamp_unix": fetch_timestamp,
                        "dequeue_monotonic": fetch_monotonic,
                        "queue_residence_ms": max(
                            0.0,
                            (fetch_monotonic - event.get("enqueue_monotonic", fetch_monotonic))
                            * 1000.0,
                        ),
                        "queue_depth_before_dequeue_batch": queue_depth_before,
                        "queue_depth_after_dequeue_batch": queue_depth_after,
                        "dequeue_position_in_batch": position,
                    }
                )
                message["event"] = event

        self.queue_metrics["fetch_calls"] += 1
        self.queue_metrics["dequeued_total"] += len(messages)
        if not messages:
            self.queue_metrics["empty_fetch_calls"] += 1
        fetch = {
            "schema_version": 1,
            "fetch_sequence": self.queue_metrics["fetch_calls"],
            "destination_island": self.island_id,
            "timestamp_unix": fetch_timestamp,
            "monotonic": fetch_monotonic,
            "queue_depth_before": queue_depth_before,
            "dequeued_count": len(messages),
            "queue_depth_after": queue_depth_after,
        }
        return {"messages": messages, "fetch": fetch}

    def get_runtime_metrics(self):
        remaining_event_records = []
        for message in self.immigrants:
            if isinstance(message, dict) and "event" in message:
                event = dict(message["event"])
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
                remaining_event_records.append(event)
        return {
            **self.queue_metrics,
            "queue_depth_at_query": len(self.immigrants),
            "queried_timestamp_unix": time.time(),
            "remaining_event_records": remaining_event_records,
        }

    def __repr__(self):
        return "Island %s" % self.island_id
