import time

import ray
from jmetal.core.solution import Solution

from islands_desync.islands.core.Migration import MigrationInfo
from islands_desync.geneticAlgorithm.migrations.ray_migration import RayMigration
from islands_desync.islands.core.Emigration import Emigration
from islands_desync.islands.core.SignalActor import SignalActor


class RayMigrationPipeline(RayMigration):
    def __init__(self, islandActor, emigration: Emigration, signal_actor: SignalActor):
        super().__init__(islandActor, emigration, signal_actor)
        self.new_individuals_refs = self.islandActor.get_immigrants.remote()

    def receive_individuals(
        self, step_num: int, evaluations: int
    ) -> tuple[list[Solution], MigrationInfo]:
        packet = ray.get(self.new_individuals_refs)
        self.new_individuals_refs = self.islandActor.get_immigrants.remote()
        return self._decode_received(packet, step_num, evaluations)

    def finalize_metrics(self):
        """Resolve, but do not refill, the final pipeline prefetch.

        The prefetch has already removed its batch from the Island actor.  By
        recording it here we can reconcile every sent/enqueued/dequeued event
        without changing which migrants the optimizer processed.
        """
        packet = ray.get(self.new_individuals_refs)
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
                    "consumer_step": None,
                    "consumer_evaluations": None,
                    "consumer_observed_timestamp_unix": time.time(),
                    "end_of_run_prefetch": True,
                }
            )
            self.queue_fetches.append(fetch)

        unprocessed = []
        for message in messages:
            if isinstance(message, dict) and "event" in message:
                event = dict(message["event"])
            else:
                _, event = self._unpack_legacy_message(message)
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
            unprocessed.append(event)

        return {
            "sent_events": self.sent_events,
            "queue_fetches": self.queue_fetches,
            "prefetched_unprocessed_events": unprocessed,
            "queued_unprocessed_events": [],
        }
