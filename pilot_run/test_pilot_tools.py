import sys
import gzip
import hashlib
import importlib
import json
import os
from pathlib import Path
import tempfile
import types
from types import SimpleNamespace
import unittest
from unittest import mock


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(PROJECT_DIR / "hpc_benchmarks"))
sys.path.insert(0, str(PROJECT_DIR / "islands_desync"))

import pilot_tools
from run_benchmark import storage_paths, topology_metrics, torus_shape
from islands_desync.geneticAlgorithm.utils.filename import Filename


class PilotContractTests(unittest.TestCase):
    def test_storage_defaults_to_scratch_and_filename_uses_results_tree(self):
        with tempfile.TemporaryDirectory() as temporary:
            args = SimpleNamespace(output_root=None, audit_root=None)
            with mock.patch.dict(os.environ, {"SCRATCH": temporary}, clear=True):
                paths = storage_paths(args)
                expected_root = Path(temporary).resolve() / "islandsEA"
                self.assertEqual(str(expected_root), paths["ISLANDS_STORAGE_ROOT"])
                self.assertEqual(
                    str(expected_root / "results" / "runs"),
                    paths["ISLANDS_RUN_OUTPUT_ROOT"],
                )
                generated = Path(
                    Filename(None, False).getpath(
                        "260913", "r01_", 200, "run", 144, "b", "t", 5, 5
                    )
                )
                self.assertTrue(
                    generated.is_relative_to(expected_root / "results" / "runs")
                )

    def test_explicit_storage_overrides_take_precedence(self):
        with tempfile.TemporaryDirectory() as temporary:
            raw = Path(temporary) / "custom-raw"
            audit = Path(temporary) / "custom-audit"
            args = SimpleNamespace(output_root=str(raw), audit_root=str(audit))
            with mock.patch.dict(os.environ, {"SCRATCH": temporary}, clear=True):
                paths = storage_paths(args)
                self.assertEqual(str(raw.resolve()), paths["ISLANDS_RUN_OUTPUT_ROOT"])
                self.assertEqual(str(audit.resolve()), paths["ISLANDS_AUDIT_ROOT"])

    def test_spec_and_arguments_are_frozen(self):
        spec = pilot_tools.load_spec()
        arguments = pilot_tools.benchmark_arguments(spec, 2)
        pairs = dict(zip(arguments[::2], arguments[1::2]))
        self.assertEqual("r01_elliptic", pairs["--problem"])
        self.assertEqual("200", pairs["--dimension"])
        self.assertEqual("144", pairs["--islands"])
        self.assertEqual("8000", pairs["--evaluations"])
        self.assertEqual("16", pairs["--population"])
        self.assertEqual("4", pairs["--offspring"])
        self.assertEqual("5", pairs["--migrants"])
        self.assertEqual("5", pairs["--interval"])
        self.assertEqual("12", pairs["--torus-rows"])
        self.assertEqual("12", pairs["--torus-columns"])
        self.assertEqual("best", pairs["--strategy"])
        self.assertEqual("plain", pairs["--acceptance"])
        self.assertEqual("2", pairs["--repeat"])

    def test_exact_torus_adjacency(self):
        adjacency = pilot_tools.expected_torus(pilot_tools.load_spec())
        self.assertEqual(144, len(adjacency))
        self.assertEqual([132, 1, 12, 11], adjacency["0"])
        self.assertEqual([131, 132, 11, 142], adjacency["143"])

    def test_explicit_shape_is_accepted(self):
        args = SimpleNamespace(
            topology="torus", torus_rows=12, torus_columns=12, islands=144
        )
        self.assertEqual(
            {"rows": 12, "columns": 12, "mode": "explicit"},
            torus_shape(args),
        )

    def test_bad_explicit_shape_is_rejected(self):
        args = SimpleNamespace(
            topology="torus", torus_rows=12, torus_columns=11, islands=144
        )
        with self.assertRaisesRegex(ValueError, "must equal"):
            torus_shape(args)

    def test_historical_torus_default_is_preserved(self):
        args = SimpleNamespace(
            topology="torus", torus_rows=None, torus_columns=None, islands=144
        )
        self.assertEqual(
            {"rows": 12, "columns": 12, "mode": "historical-default"},
            torus_shape(args),
        )

    def test_result_file_contract(self):
        spec = {"islands": 2, "expected_steps_per_island": 2}
        with tempfile.TemporaryDirectory() as temporary:
            run = Path(temporary)
            for island in range(2):
                final = 9.0 - island
                (run / f"resultsEveryStepW{island}.json").write_text(
                    json.dumps({"1": 10.0 - island, "2": final}),
                    encoding="utf-8",
                )
                (run / f"W{island} Imigrants.json").write_text("{}", encoding="utf-8")
                (run / f"kontrolW{island}End.ctrl.txt").write_text(
                    str(final), encoding="utf-8"
                )
                ranking = json.dumps([[0, 0], [0, 0]])
                (run / f"W{island}neighbourRanking.json").write_text(
                    ranking, encoding="utf-8"
                )
                (run / f"W{island}neighbourRankingPercent.json").write_text(
                    ranking, encoding="utf-8"
                )
                (run / f"W{island} set-minOS-srOS-diversity.json").write_text(
                    json.dumps(
                        {
                            "1": {"y": 2, "y2": 0.1, "y3": 0.2},
                            "2": {"y": 2, "y2": 0.1, "y3": 0.2},
                        }
                    ),
                    encoding="utf-8",
                )
            (run / "iterations_per_second.json").write_text(
                json.dumps(
                    {
                        str(island): {
                            "island": island,
                            "iterations": 2,
                            "time": 1.0,
                            "ips": 2.0,
                            "start": 1.0,
                            "end": 2.0,
                        }
                        for island in range(2)
                    }
                ),
                encoding="utf-8",
            )
            errors = []
            curves, final_results, immigrants = pilot_tools.parse_island_outputs(
                run, spec, errors
            )
            iterations = pilot_tools.check_iteration_results(run, spec, errors)
            self.assertEqual([], errors)
            self.assertEqual(2, len(curves))
            self.assertEqual(2, len(final_results))
            self.assertEqual(2, len(immigrants))
            self.assertEqual(2, len(iterations))

    def test_topology_metrics_capture_structure_and_hash(self):
        args = SimpleNamespace(
            topology="torus", torus_rows=3, torus_columns=4, islands=12
        )
        adjacency = {}
        for island in range(12):
            row = island // 4
            adjacency[island] = [
                (island - 4) % 12,
                ((island + 1) % 4) + 4 * row,
                (island + 4) % 12,
                ((island - 1) % 4) + 4 * row,
            ]
        metrics = topology_metrics(args, adjacency)
        self.assertEqual(12, metrics["node_count"])
        self.assertEqual(48, metrics["directed_edge_count_with_multiplicity"])
        self.assertEqual(0, metrics["self_loop_count_with_multiplicity"])
        self.assertTrue(metrics["strongly_connected"])
        self.assertEqual({"row": 2, "column": 3}, metrics["torus_coordinate_by_island"]["11"])

    def test_research_metrics_contract(self):
        spec = {
            "islands": 2,
            "dimension": 3,
            "population": 2,
            "evaluations_per_island": 4,
            "expected_steps_per_island": 2,
            "effect_horizon_steps": 25,
        }
        with tempfile.TemporaryDirectory() as temporary:
            run = Path(temporary)
            metrics_root = run / "metrics"
            metrics_root.mkdir()
            (metrics_root / "data_contract.json").write_text(
                json.dumps({"schema_version": 1, "legacy_outputs_preserved": True}),
                encoding="utf-8",
            )
            for island in range(2):
                directory = metrics_root / f"island_{island:03d}"
                directory.mkdir()
                variables = [float(island), 1.0, 2.0]
                variable_hash = hashlib.sha256(
                    json.dumps(variables, separators=(",", ":")).encode("utf-8")
                ).hexdigest()
                (directory / "final_solution.json").write_text(
                    json.dumps(
                        {
                            "island": island,
                            "variables": variables,
                            "variables_sha256": variable_hash,
                        }
                    ),
                    encoding="utf-8",
                )
                (directory / "runtime.json").write_text(
                    json.dumps(
                        {
                            "island": island,
                            "actual_evaluations": 4,
                            "actual_steps": 2,
                            "hostname": "node-a",
                            "ray_node_id": "node-id",
                            "queue": {
                                "received_total": 1,
                                "dequeued_total": 1,
                                "fetch_calls": 3,
                                "empty_fetch_calls": 2,
                                "maximum_queue_depth": 1,
                                "queue_depth_at_query": 0,
                            },
                        }
                    ),
                    encoding="utf-8",
                )
                (directory / "summary.json").write_text(
                    json.dumps(
                        {
                            "island": island,
                            "effect_horizon_steps": 25,
                            "sent_event_records": 1,
                            "process_event_records": 1,
                            "prefetched_unprocessed_event_records": 0,
                            "queued_unprocessed_event_records": 0,
                            "counters": {"received_before_filter": 1},
                            "queue_fetch_records": 3,
                        }
                    ),
                    encoding="utf-8",
                )
                with gzip.open(directory / "migration_events.jsonl.gz", "wt", encoding="utf-8") as output:
                    output.write(json.dumps({"record_type": "send", "event_id": f"{island}:1", "source_island": island, "destination_island": 1 - island}) + "\n")
                    output.write(json.dumps({"record_type": "process", "event_id": f"{island}:1", "source_island": island, "destination_island": 1 - island, "processed": True, "accepted_by_filter": True, "signed_delay_steps": -1}) + "\n")
                with gzip.open(directory / "queue_fetches.jsonl.gz", "wt", encoding="utf-8") as output:
                    for _ in range(3):
                        output.write("{}\n")
                with gzip.open(directory / "fitness_history.jsonl.gz", "wt", encoding="utf-8") as output:
                    for record in (
                        {"phase": "initial_population", "evaluations": 2, "best_so_far": 3.0},
                        {"phase": "after_replacement", "evaluations": 3, "best_so_far": 2.0},
                        {"phase": "after_replacement", "evaluations": 4, "best_so_far": 1.0},
                    ):
                        output.write(json.dumps(record) + "\n")
            errors = []
            overview = pilot_tools.check_research_metrics(run, spec, errors)
            self.assertEqual([], errors)
            self.assertEqual(2, overview["totals"]["send"])
            self.assertEqual(6, overview["totals"]["fitness_snapshots"])

    def test_emigration_preserves_selection_and_records_destination(self):
        sys.modules.setdefault("ray", types.ModuleType("ray"))
        from islands_desync.islands.core.Emigration import Emigration

        calls = []

        class RemoteMethod:
            def remote(self, payload):
                calls.append(payload)
                return "delivery-ref"

        class Actor:
            def __init__(self):
                self.receive_immigrant = RemoteMethod()

        class SelectSecond:
            def choose(self, items):
                self.observed_items = items
                return items[1]

        actors = [Actor(), Actor()]
        selector = SelectSecond()
        emigration = Emigration(actors, selector, [7, 11])
        original_event = {"event_id": "3:1", "source_island": 3}
        sent_event, delivery_ref = emigration.emigrate("solution", original_event)

        self.assertIs(selector.observed_items, actors)
        self.assertEqual(11, sent_event["destination_island"])
        self.assertNotIn("destination_island", original_event)
        self.assertEqual("delivery-ref", delivery_ref)
        self.assertEqual("solution", calls[0]["solution"])
        self.assertEqual(sent_event, calls[0]["event"])

    def test_empty_ray_fetch_decodes_without_exception(self):
        ray_module = sys.modules.setdefault("ray", types.ModuleType("ray"))
        ray_module.remote = lambda **_kwargs: (lambda value: value)
        jmetal = sys.modules.setdefault("jmetal", types.ModuleType("jmetal"))
        core = sys.modules.setdefault("jmetal.core", types.ModuleType("jmetal.core"))
        solution_module = sys.modules.setdefault(
            "jmetal.core.solution", types.ModuleType("jmetal.core.solution")
        )
        solution_module.Solution = type("Solution", (), {})
        jmetal.core = core
        core.solution = solution_module
        from islands_desync.geneticAlgorithm.migrations.ray_migration import (
            RayMigration,
        )

        migration = object.__new__(RayMigration)
        migration.queue_fetches = []
        individuals, info = migration._decode_received(
            {
                "messages": [],
                "fetch": {
                    "fetch_sequence": 1,
                    "destination_island": 0,
                    "queue_depth_before": 0,
                    "dequeued_count": 0,
                    "queue_depth_after": 0,
                },
            },
            step_num=1,
            evaluations=16,
        )
        self.assertEqual([], individuals)
        self.assertEqual([], info.events)
        self.assertEqual([], info.fitnesses)
        self.assertEqual(1, len(migration.queue_fetches))

    def test_parsable_sacct_cost_and_memory(self):
        with tempfile.TemporaryDirectory() as temporary:
            pilot = Path(temporary)
            rows = []
            for repeat in (1, 2, 3):
                rows.append(
                    f"123_{repeat}|job|plgrid|COMPLETED|0:0|10|336|3360|00:09:00||||2Gc|0|"
                )
                rows.append(
                    f"123_{repeat}.batch|batch||COMPLETED|0:0|10|336|3360|00:09:00|512M||||0|"
                )
            (pilot / "sacct.txt").write_text("\n".join(rows), encoding="utf-8")
            parsed = pilot_tools.parse_sacct(
                pilot, "123", {"repeats": [1, 2, 3]}
            )
            self.assertAlmostEqual(
                2.8, parsed["aggregate"]["allocated_cpu_hours"]
            )
            self.assertEqual(512 * 1024**2, parsed["aggregate"]["maximum_rss_bytes_across_steps"])
            self.assertAlmostEqual(540 / 3360, parsed["repeats"]["1"]["cpu_efficiency"])

    def test_parsable_sacct_uses_recorded_array_element_job_ids(self):
        with tempfile.TemporaryDirectory() as temporary:
            pilot = Path(temporary)
            job_ids = {1: "21083932", 2: "21083933", 3: "21083930"}
            rows = []
            for repeat, job_id in job_ids.items():
                attempt_dir = pilot / f"repeat-{repeat}"
                attempt_dir.mkdir(parents=True)
                (attempt_dir / "attempt.json").write_text(
                    json.dumps({"slurm": {"SLURM_JOB_ID": job_id}}),
                    encoding="utf-8",
                )
                rows.append(
                    f"{job_id}|job|plgrid|COMPLETED|0:0|10|336|3360|00:09:00||||672G|0|"
                )
                rows.append(
                    f"{job_id}.batch|batch||COMPLETED|0:0|10|48|480|00:01:00|512M||||0|"
                )
            (pilot / "sacct.txt").write_text("\n".join(rows), encoding="utf-8")

            parsed = pilot_tools.parse_sacct(
                pilot, "21083930", {"repeats": [1, 2, 3]}
            )

            self.assertAlmostEqual(
                2.8, parsed["aggregate"]["allocated_cpu_hours"]
            )
            for repeat, job_id in job_ids.items():
                self.assertTrue(parsed["repeats"][str(repeat)]["available"])
                self.assertEqual(job_id, parsed["repeats"][str(repeat)]["job_id"])

    def test_rich_delay_statistics(self):
        matplotlib = types.ModuleType("matplotlib")
        matplotlib.__path__ = []
        matplotlib.use = lambda *_args, **_kwargs: None
        matplotlib.cm = types.ModuleType("matplotlib.cm")
        matplotlib.colors = types.ModuleType("matplotlib.colors")
        matplotlib.pyplot = types.ModuleType("matplotlib.pyplot")
        sys.modules.setdefault("matplotlib", matplotlib)
        sys.modules.setdefault("matplotlib.cm", matplotlib.cm)
        sys.modules.setdefault("matplotlib.colors", matplotlib.colors)
        sys.modules.setdefault("matplotlib.pyplot", matplotlib.pyplot)
        analyzer = importlib.import_module("analyze_migration_delays")

        stats = analyzer.describe([-10, -1, 0, 3, 8])
        self.assertEqual(5, stats["count"])
        self.assertIn("std_ddof_0", stats)
        self.assertIn("std_ddof_1", stats)
        self.assertEqual(18.0, stats["amplitude"])
        self.assertEqual(4.0, stats["iqr"])
        split = analyzer.delay_breakdown([-11, -1, 0, 4, 12], 10)
        self.assertEqual(1, split["strongly_delayed_count"])
        self.assertEqual(1, split["strongly_accelerated_count"])


if __name__ == "__main__":
    unittest.main()
