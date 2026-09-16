"""Pure contract tests for the Athena sharded-island integration plan."""
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from athena_gpu.island_integration import (
    BACKEND_MAX_BATCH_ROWS,
    BatchPolicy,
    ResourcePlan,
    ScientificPlan,
    balanced_shard_plan,
    build_plan,
)


class IslandIntegrationPlanTests(unittest.TestCase):
    def test_full_plan_fits_one_a100_and_sixteen_cpus(self):
        plan = build_plan(ScientificPlan(), ResourcePlan(), BatchPolicy())
        self.assertEqual("athena-integration-200", plan["profile"])
        self.assertFalse(plan["approved_study_profile"])
        self.assertFalse(plan["submission_performed"])
        self.assertEqual(16, plan["resources"]["slurm_cpus"])
        self.assertEqual(15, plan["resources"]["ray_cpus"])
        self.assertEqual(15, plan["resources"]["actor_cpus"])
        self.assertEqual(1, plan["resources"]["gpus"])
        self.assertEqual(12, len(plan["shards"]))

    def test_balanced_mapping_covers_two_hundred_once(self):
        mapping = balanced_shard_plan(200, 12)
        self.assertEqual([17] * 8 + [16] * 4, [len(ids) for ids in mapping])
        self.assertEqual(list(range(200)), [island for ids in mapping for island in ids])

    def test_seed_and_evaluation_contract(self):
        scientific = ScientificPlan(repeat=3, requested_seed=100)
        plan = build_plan(scientific, ResourcePlan(), BatchPolicy())
        self.assertEqual(2_000_100, plan["scientific"]["repeat_base_seed"])
        self.assertEqual(2_000_100, plan["island_seeds"][0])
        self.assertEqual(2_000_299, plan["island_seeds"][-1])
        self.assertEqual(1_600_000, plan["scientific"]["total_evaluations"])
        self.assertEqual(3200, plan["scientific"]["initial_rows"])
        self.assertEqual(800, plan["scientific"]["ideal_steady_rows"])

    def test_full_profile_rejects_other_island_count_but_diagnostic_allows_it(self):
        scientific = ScientificPlan(logical_islands=12, evaluations_per_island=128)
        resources = ResourcePlan(island_shards=4)
        with self.assertRaisesRegex(ValueError, "exactly 200"):
            build_plan(scientific, resources, BatchPolicy())
        plan = build_plan(
            scientific,
            resources,
            BatchPolicy(initial_target_rows=192, steady_target_rows=48, max_rows=192),
            diagnostic=True,
        )
        self.assertEqual("athena-integration-diagnostic", plan["profile"])
        self.assertEqual(12, len(plan["island_to_shard"]))

    def test_resource_and_batch_guards_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "actor CPU"):
            build_plan(ScientificPlan(), ResourcePlan(island_shards=13), BatchPolicy())
        with self.assertRaisesRegex(ValueError, "hard limit"):
            build_plan(
                ScientificPlan(),
                ResourcePlan(),
                BatchPolicy(max_rows=BACKEND_MAX_BATCH_ROWS + 1),
            )
        with self.assertRaisesRegex(ValueError, "steady_target_rows"):
            build_plan(
                ScientificPlan(),
                ResourcePlan(),
                BatchPolicy(steady_target_rows=3201, max_rows=3200),
            )

    def test_phase_specific_batch_policy_matches_two_hundred_islands(self):
        plan = build_plan(ScientificPlan(), ResourcePlan(), BatchPolicy())
        self.assertEqual(3200, plan["batching"]["initial_target_rows"])
        self.assertEqual(800, plan["batching"]["steady_target_rows"])
        self.assertEqual(50.0, plan["batching"]["initial_max_wait_ms"])
        self.assertEqual(2.0, plan["batching"]["steady_max_wait_ms"])

    def test_cli_is_json_and_has_no_execution_side_effect(self):
        script = ROOT / "athena_gpu/island_integration.py"
        completed = subprocess.run(
            [sys.executable, str(script)],
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=True,
        )
        plan = json.loads(completed.stdout)
        self.assertEqual(200, plan["scientific"]["logical_islands"])
        self.assertFalse(plan["submission_performed"])


if __name__ == "__main__":
    unittest.main()
