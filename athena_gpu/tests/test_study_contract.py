"""Pure tests for the approved Athena 144-island execution contract."""
import unittest
from types import SimpleNamespace

from athena_gpu.study_contract import (
    balanced_shards,
    build_study_plan,
    deterministic_shards,
)


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
        self.assertEqual("sha256-ranked-balanced-v1", plan["shard_mapping"]["algorithm"])
        self.assertEqual(
            "rotating-round-robin-bounded-lead-v1",
            plan["scheduler"]["algorithm"],
        )
        self.assertFalse(plan["scheduler"]["generation_barrier"])
        self.assertEqual(
            0.5,
            plan["full_run_quality_gates"][
                "maximum_absolute_position_fitness_pearson"
            ],
        )

    def test_study_batch_policy_uses_attainable_rows(self):
        plan = build_study_plan()
        batching = plan["batching"]
        self.assertEqual(2304, batching["initial_target_rows"])
        self.assertEqual(144, batching["steady_target_rows"])
        self.assertEqual(2304, batching["max_rows"])
        self.assertEqual(50.0, batching["initial_max_wait_ms"])
        self.assertEqual(50.0, batching["steady_max_wait_ms"])

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

    def test_study_mapping_is_seeded_balanced_and_not_node_order(self):
        first = deterministic_shards(144, 12, mapping_seed=20260912)
        repeated = deterministic_shards(144, 12, mapping_seed=20260912)
        next_repeat = deterministic_shards(144, 12, mapping_seed=21260912)
        self.assertEqual(first, repeated)
        self.assertNotEqual(first, next_repeat)
        self.assertEqual([12] * 12, list(map(len, first)))
        self.assertEqual(list(range(144)), sorted(island for shard in first for island in shard))
        self.assertNotEqual(tuple(range(12)), first[0])

    def test_effective_metadata_replaces_legacy_strategy_and_delay_matrix(self):
        from athena_gpu.run_study import _effective_algorithm_configuration

        source = {
            "problem": "sphere",
            "number_of_variables": 10,
            "number_of_evaluations": 128,
            "population_size": 8,
            "offspring_population_size": 2,
            "number_of_islands": 10,
            "number_of_migrants": 2,
            "migration_interval": 20,
            "migrant_selection_type": "random",
            "island_delays": {"0": [-1, 0]},
        }
        args = SimpleNamespace(
            problem="r01_elliptic",
            dimension=200,
            evaluations=8000,
            population=16,
            offspring=4,
            islands=144,
            migrants=5,
            interval=5,
            strategy="best",
            acceptance="plain",
            topology="torus",
        )
        effective = _effective_algorithm_configuration(args, source)
        self.assertEqual("best", effective["migrant_selection_type"])
        self.assertEqual("plain", effective["migrant_acceptance_type"])
        self.assertEqual(144, effective["number_of_islands"])
        self.assertNotIn("island_delays", effective)
        self.assertIn("island_delays", source)


if __name__ == "__main__":
    unittest.main()
