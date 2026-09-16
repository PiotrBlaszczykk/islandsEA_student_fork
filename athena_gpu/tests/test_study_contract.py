"""Pure tests for the approved Athena 144-island execution contract."""
import unittest

from athena_gpu.study_contract import balanced_shards, build_study_plan


class StudyContractTests(unittest.TestCase):
    def test_full_profile_is_one_normal_study_run(self):
        plan = build_study_plan()
        self.assertEqual("athena-study-144", plan["profile"])
        self.assertTrue(plan["approved_study_profile"])
        self.assertEqual(144, plan["scientific"]["logical_islands"])
        self.assertEqual(1996, plan["scientific"]["expected_steps_per_island"])
        self.assertEqual(2304, plan["scientific"]["initial_rows"])
        self.assertEqual(576, plan["scientific"]["maximum_independent_steady_rows"])
        self.assertEqual(15, plan["resources"]["actor_cpus"])
        self.assertEqual([12] * 12, [len(shard["island_ids"]) for shard in plan["shards"]])

    def test_study_batch_policy_uses_attainable_rows(self):
        plan = build_study_plan()
        batching = plan["batching"]
        self.assertEqual(2304, batching["initial_target_rows"])
        self.assertEqual(576, batching["steady_target_rows"])
        self.assertEqual(2304, batching["max_rows"])
        self.assertEqual(50.0, batching["initial_max_wait_ms"])
        self.assertEqual(2.0, batching["steady_max_wait_ms"])

    def test_nonstudy_count_is_fail_closed_without_diagnostic(self):
        with self.assertRaisesRegex(ValueError, "144"):
            build_study_plan(islands=12, shards=4, evaluations=128)
        plan = build_study_plan(
            islands=12,
            shards=4,
            evaluations=128,
            diagnostic=True,
        )
        self.assertEqual("athena-study-diagnostic", plan["profile"])
        self.assertFalse(plan["approved_study_profile"])
        self.assertEqual(7, plan["resources"]["actor_cpus"])
        self.assertEqual(192, plan["batching"]["initial_target_rows"])
        self.assertEqual(48, plan["batching"]["steady_target_rows"])

    def test_mapping_is_stable_and_exact(self):
        mapping = balanced_shards(17, 4)
        self.assertEqual([5, 4, 4, 4], list(map(len, mapping)))
        self.assertEqual(list(range(17)), [island for shard in mapping for island in shard])


if __name__ == "__main__":
    unittest.main()
