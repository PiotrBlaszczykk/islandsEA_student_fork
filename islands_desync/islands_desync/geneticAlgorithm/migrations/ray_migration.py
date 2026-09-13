import os
import time

import ray

from jmetal.core.solution import Solution

from islands_desync.islands.core.Emigration import Emigration
from islands_desync.islands.core.Migration import Migration
from islands_desync.islands.core.SignalActor import SignalActor
from islands_desync.islands.core.Migration import MigrationInfo


class RayMigration(Migration):
    def __init__(self, islandActor, emigration: Emigration, signal_actor: SignalActor):
        super().__init__()
        self.emigration = emigration
        self.islandActor = islandActor
        self.signal_actor: SignalActor = signal_actor
        self.sent_events: list[dict] = []
        self.queue_fetches: list[dict] = []
        self.send_sequence = 0
        # Ray actor calls from one submitter to one destination are ordered.
        # Retaining only the latest ref per destination is therefore enough to
        # acknowledge all earlier sends without keeping ~1M refs cluster-wide.
        self.latest_delivery_refs = {}

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
        # print("Emigracja %s iter: %s" % (island_number, iteration_number))
        batch_id = f"{src_island}:{iteration_number}"
        for batch_position, individual in enumerate(individuals_to_migrate):
            # print("%s: Emigruje %s" % (self.islandActor, individual))
            self.send_sequence += 1
            event = {
                "schema_version": 1,
                "event_id": f"{src_island}:{self.send_sequence}",
                "batch_id": batch_id,
                "batch_position": batch_position,
                "batch_size": len(individuals_to_migrate),
                "source_island": src_island,
                "source_step": iteration_number,
                "source_evaluations": evaluations,
                "fitness_at_send": float(individual.objectives[0]),
                "source_best_at_send": source_best,
                "solution_origin_island": getattr(individual, "from_island", None),
                "solution_origin_evaluation": getattr(
                    individual, "from_evaluation", None
                ),
                "send_timestamp_unix": ind_timestamp,
                "send_monotonic": time.monotonic(),
                "record_type": "send",
                "dispatch_status": "submitted_to_ray_actor",
            }
            sent_event, delivery_ref = self.emigration.emigrate(individual, event)
            self.sent_events.append(sent_event)
            self.latest_delivery_refs[sent_event["destination_island"]] = delivery_ref

    @staticmethod
    def _unpack_legacy_message(message):
        individual, iteration, timestamp, source, fitness = message
        return individual, {
            "schema_version": 0,
            "event_id": None,
            "batch_id": None,
            "source_island": source,
            "source_step": iteration,
            "source_evaluations": None,
            "fitness_at_send": fitness,
            "send_timestamp_unix": timestamp,
            "record_type": "legacy_receive",
        }

    def _decode_received(self, packet, step_num: int, evaluations: int):
        if isinstance(packet, dict) and "messages" in packet:
            messages = packet["messages"]
            fetch = packet.get("fetch")
        else:
            messages = packet
            fetch = None

        if fetch is not None:
            fetch = dict(fetch)
            fetch.update(
                {
                    "consumer_step": step_num,
                    "consumer_evaluations": evaluations,
                    "consumer_observed_timestamp_unix": time.time(),
                }
            )
            self.queue_fetches.append(fetch)

        individuals = []
        events = []
        for message in messages:
            if isinstance(message, dict) and "solution" in message and "event" in message:
                individual = message["solution"]
                event = dict(message["event"])
            else:
                individual, event = self._unpack_legacy_message(message)
            individuals.append(individual)
            events.append(event)

        migration_info = MigrationInfo(
            step=step_num,
            ev=evaluations,
            iteration_numbers=[event["source_step"] for event in events],
            timestamps=[event["send_timestamp_unix"] for event in events],
            src_islands=[event["source_island"] for event in events],
            fitnesses=[event["fitness_at_send"] for event in events],
            events=events,
            fetch=fetch,
        )
        return individuals, migration_info

    def receive_individuals(
        self, step_num: int, evaluations: int
    ) -> tuple[list[Solution], MigrationInfo]:
        packet = ray.get(self.islandActor.get_immigrants.remote())
        return self._decode_received(packet, step_num, evaluations)

    def finalize_metrics(self):
        return {
            "sent_events": self.sent_events,
            "queue_fetches": self.queue_fetches,
            "prefetched_unprocessed_events": [],
            "queued_unprocessed_events": [],
        }

    def wait_for_outgoing_deliveries(self):
        if self.latest_delivery_refs:
            ray.get(
                list(self.latest_delivery_refs.values()),
                timeout=float(
                    os.environ.get("ISLANDS_DELIVERY_TIMEOUT_SECONDS", "300")
                ),
            )
        self.signal_actor.send.remote("delivery")
        ray.get(self.signal_actor.wait.remote("delivery"))

    def wait_for_all_start(self):
        self.signal_actor.send.remote()
        ray.get(self.signal_actor.wait.remote())

    def wait_for_finish(self):
        ray.get(self.signal_actor.wait.remote("finish"))

    def signal_finish(self):
        self.signal_actor.send.remote("finish")
