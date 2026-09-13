import ray

from islands_desync.islands.selectAlgorithm import SelectAlgorithm


class Emigration:
    def __init__(
        self,
        islands,
        select_algorithm: SelectAlgorithm,
        destination_island_ids=None,
    ):
        self.islands = islands
        self.select_algorithm: SelectAlgorithm = select_algorithm
        self.destination_island_ids = (
            list(range(len(islands)))
            if destination_island_ids is None
            else list(destination_island_ids)
        )
        if len(self.destination_island_ids) != len(self.islands):
            raise ValueError("Every migration destination must have an island id")

    def emigrate(self, population_member, event):
        """Dispatch one migrant and return the exact send-side event record.

        Destination selection still receives the original actor-handle list, so
        adding telemetry does not consume a different random number or change
        the migration policy.
        """
        destination = self.select_algorithm.choose(self.islands)
        destination_index = self.islands.index(destination)
        send_event = dict(event)
        send_event["destination_island"] = self.destination_island_ids[
            destination_index
        ]
        delivery_ref = destination.receive_immigrant.remote(
            {"solution": population_member, "event": send_event}
        )
        return send_event, delivery_ref
