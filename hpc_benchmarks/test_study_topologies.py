"""The selected study graphs and topology provenance, without Ray or CUDA."""
import contextlib
import hashlib
import importlib
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "islands_desync"))
sys.path.insert(0, str(ROOT / "hpc_benchmarks"))
from islands_desync.islands.topologies.fixed_graph import load_graph, graph_parameters
from islands_desync.islands.topologies.study import TOPOLOGIES, validate_study
import run_benchmark as launcher


def graph(name, count=144, callback=lambda i: i):
    cls_name = TOPOLOGIES[name]
    cls = getattr(importlib.import_module("islands_desync.islands.topologies." + cls_name), cls_name)
    with contextlib.redirect_stdout(io.StringIO()):
        instance = cls(count, callback)
        return instance.create(12, 12) if name == "torus" else instance.create()


class StudyTopologyTests(unittest.TestCase):
    def test_default_study_contract_and_diagnostic_escape(self):
        args = launcher.parser().parse_args(["--problem", "r01_elliptic", "--dimension", "200"])
        self.assertEqual(144, args.islands)
        self.assertEqual(200, args.dimension)
        for name in ("torus", "complete", "ws3", "ba", "er4"):
            validate_study(144, name)
            for n in (2, 150, 180, 200):
                with self.subTest(name=name, n=n), self.assertRaisesRegex(ValueError, "exactly 144"):
                    validate_study(n, name)
        for name in ("er1", "er2", "er3", "ws4"):
            with self.assertRaises(ValueError):
                validate_study(144, name)
        with self.assertRaises(ValueError):
            validate_study(144, "ring")
        validate_study(2, "ring", diagnostic=True)

    def test_all_ready_graphs_have_exactly_144_valid_connected_nodes(self):
        for name, directed_edges in (("torus", 576), ("complete", 20592), ("ws3", 3606), ("ba", 7710), ("er4", 730)):
            with self.subTest(name=name):
                adjacency = graph(name)
                self.assertEqual(set(range(144)), set(adjacency))
                self.assertEqual(directed_edges, sum(map(len, adjacency.values())))
                for i, targets in adjacency.items():
                    self.assertNotIn(i, targets)
                    self.assertEqual(len(targets), len(set(targets)))
                    for target in targets:
                        self.assertIn(target, adjacency)
                        self.assertIn(i, adjacency[target])
                seen, pending = {0}, [0]
                while pending:
                    for target in adjacency[pending.pop()]:
                        if target not in seen:
                            seen.add(target)
                            pending.append(target)
                self.assertEqual(144, len(seen))

    def test_torus_wrap_and_neighbour_order(self):
        adjacency = graph("torus")
        self.assertEqual([132, 1, 12, 11], adjacency[0])
        self.assertEqual([131, 132, 11, 142], adjacency[143])

    def test_fixed_graph_order_and_actor_handle_mapping(self):
        handles = [object() for _ in range(144)]
        for name in ("ws3", "ba", "er4"):
            original = load_graph(name)["adjacency"]
            converted = graph(name, callback=lambda i: (i, handles[i]))
            for source, neighbours in original.items():
                self.assertEqual(neighbours, [i for i, _ in converted[int(source)]])
                self.assertTrue(all(handle is handles[i] for i, handle in converted[int(source)]))

    def test_fixed_graph_rejects_all_wrong_sizes_without_callback_side_effects(self):
        for name in ("ws3", "ba", "er4"):
            for size in (1, 143, 145, 150, 200):
                with self.subTest(name=name, size=size), self.assertRaisesRegex(ValueError, "144 nodes"):
                    graph(name, size, callback=lambda _: self.fail("No actor lookup before graph validation"))

    def test_er4_matches_authorized_generation_contract(self):
        document = load_graph("er4")
        adjacency = document["adjacency"]
        self.assertEqual(144, document["nodes"])
        self.assertEqual(730, sum(map(len, adjacency.values())))
        self.assertEqual(0, sum(int(i) in targets for i, targets in adjacency.items()))
        self.assertEqual(0.0347, document["parameters"]["probab"])
        self.assertIs(document["parameters"]["directed"], False)
        self.assertEqual(20260917, document["provenance"]["generator"]["selected_seed"])
        self.assertEqual("469cc283543dcc60d5bf8f07db2eabfb12cab34637f4a6d26bca51d07f85cccc",
                         document["provenance"]["adjacency_sha256"])
        self.assertEqual({int(i): targets for i, targets in adjacency.items()}, graph("er4"))

    def test_changed_adjacency_fails_checksum(self):
        altered = load_graph("ba")
        altered["adjacency"]["0"].reverse()
        with patch("pathlib.Path.read_text", return_value=json.dumps(altered)):
            with self.assertRaisesRegex(ValueError, "checksum"):
                load_graph("ba")

    def test_provenance_is_preserved_in_saved_topology(self):
        for name in ("ws3", "ba", "er4"):
            args = launcher.parser().parse_args(["--problem", "r01_elliptic", "--dimension", "200", "--topology", name])
            payload = launcher.topology_payload(args, graph(name))
            self.assertEqual(graph_parameters(name), payload["parameters"])
            self.assertEqual(payload["parameters"]["provenance"]["adjacency_sha256"], payload["graph_metrics"]["adjacency_sha256"])
            self.assertEqual(load_graph(name)["provenance"], payload["parameters"]["provenance"])

    def test_pilot_cpu_profile_and_budget(self):
        spec = json.loads((ROOT / "pilot_run/pilot_spec.json").read_text())
        self.assertEqual((144, 200, 12, 12), (spec["islands"], spec["dimension"], spec["torus_rows"], spec["torus_columns"]))
        cpus = spec["slurm"]["nodes_per_repeat"] * spec["slurm"]["cpus_per_node"]
        self.assertEqual(336, cpus)
        self.assertGreaterEqual(cpus, 2 * spec["islands"] + 2)
        self.assertEqual(1152000, spec["islands"] * spec["evaluations_per_island"])


if __name__ == "__main__":
    unittest.main()
