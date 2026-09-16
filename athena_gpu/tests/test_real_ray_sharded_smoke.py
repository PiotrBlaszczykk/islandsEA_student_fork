"""Opt-in local Ray smoke for the sharded scheduler (NumPy evaluator only).

This is deliberately excluded from normal discovery unless
``ISLANDS_RUN_RAY_SMOKE=1``.  It exercises actor concurrency and the complete
GA/migration/batcher lifecycle, but it is not evidence for CuPy or Athena.
"""
from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
import sys
import tempfile
import unittest
import uuid


ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = ROOT / "islands_desync"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(PACKAGE_ROOT))


@unittest.skipUnless(
    os.environ.get("ISLANDS_RUN_RAY_SMOKE") == "1",
    "set ISLANDS_RUN_RAY_SMOKE=1 for the real local Ray smoke",
)
class RealRayShardedSmokeTests(unittest.TestCase):
    def test_four_logical_islands_complete_without_generation_barrier(self):
        import ray

        from athena_gpu.evaluation_batcher import make_actor_class as make_batcher
        from athena_gpu.island_shard import make_actor_class as make_island_shard
        from athena_gpu.migration_router import make_actor_class as make_router
        from athena_gpu.study_contract import build_study_plan
        from hpc_benchmarks import run_benchmark as common
        from islands_desync.geneticAlgorithm.run_hpc.run_algorithm_params import (
            RunAlgorithmParams,
        )

        arguments = common.parser().parse_args(
            [
                "--problem", "r01_elliptic",
                "--dimension", "10",
                "--islands", "4",
                "--diagnostic",
                "--evaluations", "32",
                "--population", "16",
                "--offspring", "4",
                "--migrants", "5",
                "--interval", "5",
                "--topology", "torus",
                "--torus-rows", "2",
                "--torus-columns", "2",
                "--strategy", "best",
                "--acceptance", "plain",
                "--repeat", "1",
                "--seed", "20260912",
                "--ray-address", "local",
                "--local-cpus", "5",
            ]
        )
        _, _, _, adjacency = common.validate(arguments)
        plan = build_study_plan(
            islands=4,
            shards=2,
            population=16,
            offspring=4,
            evaluations=32,
            diagnostic=True,
            initial_max_wait_ms=50,
            steady_max_wait_ms=5,
        )
        with tempfile.TemporaryDirectory(
            prefix="athena-shard-ray-", ignore_cleanup_errors=True
        ) as temporary:
            root = Path(temporary).resolve()
            arguments.output_root = str(root / "runs")
            arguments.audit_root = str(root / "audit")
            environment = common.environment(arguments)
            previous = {name: os.environ.get(name) for name in environment}
            os.environ.update(environment)
            try:
                for name in (
                    "ISLANDS_RUN_OUTPUT_ROOT",
                    "ISLANDS_AUDIT_ROOT",
                    "ISLANDS_TMP_ROOT",
                    "MPLCONFIGDIR",
                    "XDG_CACHE_HOME",
                    "RAY_TMPDIR",
                ):
                    Path(environment[name]).mkdir(parents=True, exist_ok=True)
                ray.init(
                    address="local",
                    num_cpus=5,
                    include_dashboard=False,
                    _temp_dir=str(root / "ray"),
                    runtime_env={"env_vars": environment},
                )

                @ray.remote(num_cpus=1, max_restarts=0, max_task_retries=0)
                class NumpyEvaluator:
                    def __init__(self):
                        from islands_desync.geneticAlgorithm.utils.benchmarks_refined.batch import (
                            NumpyBatchBackend,
                        )

                        self.backend = NumpyBatchBackend(max_batch_size=64)

                    def evaluate(self, problem_id, vectors, *, instance_seed):
                        values = self.backend.evaluate_batch(
                            problem_id, vectors, instance_seed=instance_seed
                        )
                        return {
                            "values": values,
                            "profile": {
                                **self.backend.last_profile,
                                "h2d_count": 1,
                                "d2h_count": 1,
                                "kernel_device_seconds": 1e-9,
                                "test_backend": "numpy",
                            },
                        }

                EvaluationBatcher = make_batcher()
                MigrationRouter = make_router()
                IslandShard = make_island_shard()
                evaluator = NumpyEvaluator.remote()
                router = MigrationRouter.remote(4)
                batcher = EvaluationBatcher.remote(
                    evaluator,
                    initial_target_rows=64,
                    steady_target_rows=16,
                    max_rows=64,
                    initial_max_wait_ms=50,
                    steady_max_wait_ms=5,
                )
                now = datetime.now()
                params = RunAlgorithmParams(
                    4,
                    5,
                    5,
                    now.strftime("%y%m%d"),
                    now.strftime("%H%M%S") + "_" + uuid.uuid4().hex[:8],
                    1,
                    "torus",
                    "best",
                    "plain",
                    torus_rows=2,
                    torus_columns=2,
                    actor_startup_timeout=120,
                )
                shards = [
                    IslandShard.remote(
                        shard_id=item["shard_id"],
                        island_ids=item["island_ids"],
                        adjacency=adjacency,
                        run_params=params.__dict__,
                        run_id="local-ray-sharded-smoke",
                        problem_id="r01_elliptic",
                        dimension=10,
                        instance_seed=20260511,
                        batcher=batcher,
                        router=router,
                        package_root=str(PACKAGE_ROOT),
                        operation_timeout_seconds=120,
                    )
                    for item in plan["shards"]
                ]
                first = ray.get(shards[0].prepare_island_zero.remote(), timeout=120)
                ray.get([shard.prepare_remaining.remote() for shard in shards], timeout=120)
                ray.get([shard.initialize.remote() for shard in shards], timeout=120)
                ray.get([shard.run.remote() for shard in shards], timeout=120)
                summary = ray.get(batcher.flush.remote(), timeout=120)
                ray.get([shard.acknowledge_deliveries.remote() for shard in shards], timeout=120)
                results = ray.get([shard.finalize.remote() for shard in shards], timeout=120)
                router_summary = ray.get(router.summary.remote(), timeout=120)

                flattened = sorted(
                    (item for group in results for item in group),
                    key=lambda item: item["island"],
                )
                self.assertEqual([0, 1, 2, 3], [item["island"] for item in flattened])
                self.assertTrue(all(item["evaluations"] == 32 for item in flattened))
                self.assertTrue(all(item["iterations"] == 4 for item in flattened))
                self.assertEqual(20, summary["request_count"])
                self.assertEqual(128, summary["row_count"])
                self.assertEqual(0, summary["error_count"])
                self.assertEqual([0, 1, 2, 3], router_summary["finished_islands"])
                self.assertEqual([0, 1, 2, 3], router_summary["delivery_complete_islands"])
                run_directory = Path(first["run_directory"])
                self.assertTrue(run_directory.is_dir())
                import analyze_migration_delays as analyzer

                integrity = analyzer.load_research_overview(run_directory)["event_integrity"]
                self.assertGreater(integrity["sent_records"], 0)
                self.assertEqual(integrity["sent_records"], integrity["process_records"])
                self.assertEqual(0, integrity["duplicate_sent_event_ids"])
                self.assertEqual(0, integrity["duplicate_process_event_ids"])
                self.assertEqual(0, integrity["sent_without_process_record_count"])
                self.assertEqual(0, integrity["process_without_send_record_count"])
            finally:
                ray.shutdown()
                for name, value in previous.items():
                    if value is None:
                        os.environ.pop(name, None)
                    else:
                        os.environ[name] = value


if __name__ == "__main__":
    unittest.main()
