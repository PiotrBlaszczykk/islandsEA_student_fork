"""Unit tests for request, queue, RNG and split-step invariants."""
import ast
import json
from pathlib import Path
import random
import tempfile
import unittest

import numpy as np

from athena_gpu.evaluation_batcher import request_group_key, validate_request
from athena_gpu.island_shard import (
    bounded_lead_eligible,
    execute_with_rng_states,
    rotated_order,
)
from athena_gpu.migration_router import historical_drain


ROOT = Path(__file__).resolve().parents[2]


def request(**updates):
    value = {
        "schema_version": 1,
        "request_id": "run:0:1",
        "run_id": "run",
        "island_id": 0,
        "shard_id": 0,
        "phase": "offspring",
        "step": 1,
        "evaluations_before": 16,
        "problem_id": "R01_ELLIPTIC",
        "dimension": 3,
        "instance_seed": 20260511,
        "rows": 2,
        "row_context": [
            {"index": 0, "logical_evaluation": 16},
            {"index": 1, "logical_evaluation": 17},
        ],
    }
    value.update(updates)
    return value


class ShardedContractTests(unittest.TestCase):
    def test_rotating_order_gives_every_position_the_first_slot(self):
        order = (7, 3, 11, 2)
        self.assertEqual(
            [7, 3, 11, 2],
            [rotated_order(order, cursor)[0] for cursor in range(len(order))],
        )

    def test_bounded_lead_preserves_asynchrony_without_runaway(self):
        steps = {0: 0, 1: 1, 2: 2}
        self.assertEqual(
            {0, 1},
            bounded_lead_eligible(
                (0, 1, 2),
                steps,
                set(),
                maximum_completed_step_lead=2,
            ),
        )
        self.assertEqual(
            {1},
            bounded_lead_eligible(
                (0, 1, 2),
                steps,
                {0},
                maximum_completed_step_lead=2,
            ),
        )
        self.assertEqual(
            {0},
            bounded_lead_eligible(
                (0, 1, 2),
                steps,
                set(),
                maximum_completed_step_lead=1,
            ),
        )

    def test_full_validator_rejects_a_repeated_shard_position_stripe(self):
        from athena_gpu.validate_study_run import _scheduler_quality

        shards = []
        results = {}
        for shard_id in range(12):
            islands = list(range(shard_id * 12, (shard_id + 1) * 12))
            shards.append(
                {
                    "shard_id": shard_id,
                    "islands": islands,
                    "scheduler_order": islands,
                    "scheduler": {
                        "algorithm": "rotating-round-robin-bounded-lead-v1"
                    },
                }
            )
            for position, island in enumerate(islands):
                results[str(island)] = {
                    "final_fitness": float(12 - position),
                    "time": float(position + 1),
                    "shard_position": position,
                }
        with tempfile.TemporaryDirectory() as temporary:
            raw = Path(temporary)
            (raw / "iterations_per_second.json").write_text(
                json.dumps(results), encoding="utf-8"
            )
            errors = []
            quality = _scheduler_quality(raw, shards, "full", errors)
        self.assertLess(quality["position_vs_final_fitness_pearson"], -0.99)
        self.assertGreater(quality["position_vs_wall_time_pearson"], 0.99)
        self.assertTrue(any("correlated" in error for error in errors))
        self.assertTrue(any("shard winners" in error for error in errors))

    def test_request_validation_and_grouping(self):
        normalized, values = validate_request(
            request(),
            np.asarray([[1, 2, 3], [4, 5, 6]], dtype=np.float64),
            max_rows=2304,
        )
        self.assertEqual("r01_elliptic", normalized["problem_id"])
        self.assertTrue(values.flags.c_contiguous)
        self.assertEqual(
            ("offspring", "r01_elliptic", 3, 20260511, "float64"),
            request_group_key(normalized),
        )

    def test_request_validation_rejects_shape_phase_and_oversize(self):
        with self.assertRaisesRegex(ValueError, "shape"):
            validate_request(request(), np.zeros((3, 3)), max_rows=2304)
        with self.assertRaisesRegex(ValueError, "phase"):
            validate_request(request(phase="wrong"), np.zeros((2, 3)), max_rows=2304)
        with self.assertRaisesRegex(ValueError, "max_rows"):
            validate_request(
                request(rows=2305, row_context=[{}] * 2305),
                np.zeros((2305, 3)),
                max_rows=2304,
            )

    def test_router_retains_historical_partial_drain(self):
        queue = [0, 1, 2, 3, 4]
        self.assertEqual([0, 1, 2], historical_drain(queue))
        self.assertEqual([3, 4], queue)

    @staticmethod
    def _seed_states(seed):
        outer_python = random.getstate()
        outer_numpy = np.random.get_state()
        random.seed(seed)
        np.random.seed(seed)
        states = random.getstate(), np.random.get_state()
        random.setstate(outer_python)
        np.random.set_state(outer_numpy)
        return states

    @staticmethod
    def _draw():
        return random.random(), float(np.random.random())

    def test_rng_streams_are_independent_of_interleaving(self):
        states = {island: list(self._seed_states(100 + island)) for island in (0, 1)}
        interleaved = {0: [], 1: []}
        for island in (0, 1, 1, 0, 1, 0):
            value, python_state, numpy_state = execute_with_rng_states(
                states[island][0], states[island][1], self._draw
            )
            states[island] = [python_state, numpy_state]
            interleaved[island].append(value)

        isolated = {}
        for island in (0, 1):
            python_state, numpy_state = self._seed_states(100 + island)
            isolated[island] = []
            for _ in range(3):
                value, python_state, numpy_state = execute_with_rng_states(
                    python_state, numpy_state, self._draw
                )
                isolated[island].append(value)
        self.assertEqual(isolated, interleaved)

    def test_cpu_step_is_a_thin_split_step_wrapper(self):
        path = (
            ROOT
            / "islands_desync/islands_desync/geneticAlgorithm/algorithm/genetic_island_algorithm.py"
        )
        tree = ast.parse(path.read_text(encoding="utf-8"))
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "GeneticIslandAlgorithm")
        methods = {node.name: node for node in cls.body if isinstance(node, ast.FunctionDef)}
        self.assertIn("prepare_step_for_evaluation", methods)
        self.assertIn("complete_step_after_evaluation", methods)
        step = methods["step"]
        calls = [
            node.func.attr
            for node in ast.walk(step)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        ]
        self.assertEqual(
            ["prepare_step_for_evaluation", "evaluate", "complete_step_after_evaluation"],
            calls,
        )


if __name__ == "__main__":
    unittest.main()
