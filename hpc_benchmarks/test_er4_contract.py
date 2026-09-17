"""Exercise isolated-node/rejection branches even though the fixed graph is connected."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "islands_desync"))
sys.path.insert(0, str(ROOT / "hpc_benchmarks"))
from islands_desync.islands.topologies.er4_contract import (
    add_isolate_loops, inspect_adjacency, validate_er4,
)
from islands_desync.islands.topologies.fixed_graph import load_graph
from generate_er4 import select_candidate


def ring_with_isolates(count):
    size = 144 - count
    return {i: sorted([(i - 1) % size, (i + 1) % size]) if i < size else [] for i in range(144)}


def document(adjacency):
    result = copy.deepcopy(load_graph("er4"))
    result["adjacency"] = {str(i): targets for i, targets in adjacency.items()}
    result["provenance"]["graph_statistics"] = inspect_adjacency(adjacency)
    return result


class ERContractTests(unittest.TestCase):
    def test_zero_to_three_isolates_get_exactly_one_loop(self):
        for count in (0, 1, 2, 3):
            with self.subTest(count=count):
                raw = ring_with_isolates(count)
                before = copy.deepcopy(raw)
                repaired = add_isolate_loops(raw)
                self.assertEqual(before, raw)
                self.assertEqual(list(range(144 - count, 144)), inspect_adjacency(repaired)["self_loop_vertices"])
                for i in range(144 - count, 144):
                    self.assertEqual([i], repaired[i])
                self.assertEqual(144 - count, validate_er4(document(repaired))["largest_component_size"])

    def test_first_acceptable_draw_used_without_forcing_connectivity(self):
        calls = []
        def draw(seed):
            calls.append(seed)
            return ring_with_isolates(4 if len(calls) == 1 else 3)
        adjacency, attempts = select_candidate(draw, base_seed=100, max_attempts=2)
        self.assertEqual([100, 101], calls)
        self.assertEqual([False, True], [a["accepted"] for a in attempts])
        self.assertEqual([141, 1, 1, 1], inspect_adjacency(adjacency)["component_sizes"])

    def test_rejection_limit_is_bounded(self):
        with self.assertRaisesRegex(RuntimeError, "2 attempts"):
            select_candidate(lambda _: ring_with_isolates(4), max_attempts=2)

    def test_outside_largest_count_includes_nonisolated_components(self):
        raw = ring_with_isolates(4)
        for i in range(140, 144):
            raw[i] = [140 + ((i - 140 - 1) % 4), 140 + ((i - 140 + 1) % 4)]
        self.assertEqual([], inspect_adjacency(raw)["isolated_vertices_before_loops"])
        with self.assertRaisesRegex(ValueError, "outside the largest"):
            validate_er4(document(raw))

    def test_nonisolated_loop_is_rejected(self):
        value = document(add_isolate_loops(ring_with_isolates(1)))
        value["adjacency"]["0"].append(0)
        with self.assertRaisesRegex(ValueError, "none elsewhere"):
            validate_er4(value)

    def test_missing_isolate_loop_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "exactly one self-loop"):
            validate_er4(document(ring_with_isolates(1)))

    def test_asymmetry_and_duplicate_neighbours_are_rejected(self):
        raw = ring_with_isolates(0)
        raw[0].remove(1)
        with self.assertRaisesRegex(ValueError, "symmetric"):
            inspect_adjacency(raw)
        raw = ring_with_isolates(0)
        raw[0].append(raw[0][0])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            inspect_adjacency(raw)

    def test_wrong_parameters_or_stale_statistics_are_rejected(self):
        for field, value in (("n", 150), ("probab", None), ("probab", 0.04), ("directed", True), ("self_loop_policy", "all")):
            changed = copy.deepcopy(load_graph("er4"))
            changed["parameters"][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                validate_er4(changed)
        changed = copy.deepcopy(load_graph("er4"))
        changed["provenance"]["graph_statistics"]["largest_component_size"] = 143
        with self.assertRaisesRegex(ValueError, "statistics"):
            validate_er4(changed)

    def test_legacy_graph_is_archived_separately(self):
        path = ROOT / "islands_desync/islands_desync/islands/topologies/data/archive/er4_legacy150.json"
        legacy = json.loads(path.read_text())
        self.assertEqual(150, legacy["nodes"])
        self.assertEqual(load_graph("er4")["provenance"]["supersedes"]["adjacency_sha256"], legacy["provenance"]["adjacency_sha256"])


if __name__ == "__main__":
    unittest.main()
