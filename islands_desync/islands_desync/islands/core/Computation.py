import os
import socket
import time

import ray

from islands_desync.geneticAlgorithm.migrations.ray_migration_pipeline import (
    RayMigrationPipeline,
)
from islands_desync.geneticAlgorithm.run_hpc.create_algorithm_hpc import (
    create_algorithm_hpc,
)
from islands_desync.geneticAlgorithm.run_hpc.run_algorithm_params import (
    RunAlgorithmParams,
)
from islands_desync.islands.core.Emigration import Emigration
from islands_desync.islands.core.SignalActor import SignalActor


@ray.remote(num_cpus=1)
class Computation:
    def __init__(
        self,
        island,
        n: int,
        islands,
        destination_island_ids,
        select_algorithm,
        algorithm_params: RunAlgorithmParams,
        signal_actor: SignalActor
    ):
        self.island = island
        self.n: int = n
        self.constructed_timestamp_unix = time.time()
        self.hostname = socket.gethostname()
        self.pid = os.getpid()
        try:
            self.ray_node_id = str(ray.get_runtime_context().get_node_id())
        except Exception:
            self.ray_node_id = None

        self.emigration = Emigration(
            islands,
            select_algorithm,
            destination_island_ids,
        )
        self.migration = RayMigrationPipeline(island, self.emigration, signal_actor)

        self.algorithm = create_algorithm_hpc(n, self.migration, algorithm_params)

    def ready(self):
        """Acknowledge that the actor constructor and its output setup completed."""
        return self.n

    def start(self):
        print("Starting comp")
        algorithm_start = time.time()
        self.algorithm.run()
        algorithm_compute_end = time.time()
        # Island 0 already waits in the historical finalization path.  Making
        # the same phase boundary explicit for every computation prevents fast
        # actors from exporting their end-state while peers are still evolving.
        self.migration.wait_for_finish()
        finish_barrier_end = time.time()
        # A second, end-only barrier acknowledges the latest send to every
        # destination.  Because actor calls are FIFO per sender/destination,
        # this closes all delivery streams before queue snapshots are taken.
        self.migration.wait_for_outgoing_deliveries()
        delivery_barrier_end = time.time()
        result = self.algorithm.get_result()

        metrics_export_start = time.time()
        migration_telemetry = self.migration.finalize_metrics()
        island_queue_metrics = ray.get(self.island.get_runtime_metrics.remote())
        migration_telemetry["queued_unprocessed_events"] = island_queue_metrics.pop(
            "remaining_event_records", []
        )
        runtime_metrics = {
            "schema_version": 1,
            "island": self.n,
            "hostname": self.hostname,
            "pid": self.pid,
            "ray_node_id": self.ray_node_id,
            "constructed_timestamp_unix": self.constructed_timestamp_unix,
            "algorithm_start_timestamp_unix": algorithm_start,
            "algorithm_compute_end_timestamp_unix": algorithm_compute_end,
            "finish_barrier_end_timestamp_unix": finish_barrier_end,
            "delivery_barrier_end_timestamp_unix": delivery_barrier_end,
            "algorithm_wall_seconds": algorithm_compute_end - algorithm_start,
            "finish_barrier_wait_seconds": finish_barrier_end - algorithm_compute_end,
            "delivery_ack_and_barrier_seconds": (
                delivery_barrier_end - finish_barrier_end
            ),
            "migration_measurement_start_timestamp_unix": self.migration.start,
            "migration_measurement_end_timestamp_unix": self.migration.end,
            "actual_evaluations": self.algorithm.evaluations,
            "actual_steps": self.algorithm.step_num,
            "queue": island_queue_metrics,
        }
        self.algorithm.export_research_metrics(
            migration_telemetry=migration_telemetry,
            runtime_metrics=runtime_metrics,
        )
        metrics_export_end = time.time()
        runtime_metrics["metrics_export_start_timestamp_unix"] = metrics_export_start
        runtime_metrics["metrics_export_end_timestamp_unix"] = metrics_export_end
        runtime_metrics["metrics_export_wall_seconds"] = (
            metrics_export_end - metrics_export_start
        )
        # Rewrite only the compact summary with the measured export duration.
        self.algorithm.write_runtime_metrics(runtime_metrics)

        calculations = {
            "island": self.n,
            "iterations": self.algorithm.step_num,
            "time": self.migration.run_time(),
            "ips": self.algorithm.step_num / self.migration.run_time(),
            "start": self.migration.start,
            "end": self.migration.end,
            "evaluations": self.algorithm.evaluations,
            "final_fitness": float(result.objectives[0]),
            "hostname": self.hostname,
            "pid": self.pid,
            "ray_node_id": self.ray_node_id,
            "sent_migrant_count": len(migration_telemetry["sent_events"]),
            "processed_migrant_count": len(self.algorithm.processed_migration_events),
            "prefetched_unprocessed_migrant_count": len(
                migration_telemetry["prefetched_unprocessed_events"]
            ),
            "queued_unprocessed_migrant_count": len(
                migration_telemetry["queued_unprocessed_events"]
            ),
            "queue_depth_at_end": island_queue_metrics["queue_depth_at_query"],
            "metrics_export_time": metrics_export_end - metrics_export_start,
        }

        print(f"\nIsland: {self.n} Fitness: {result.objectives[0]}")

        return calculations
