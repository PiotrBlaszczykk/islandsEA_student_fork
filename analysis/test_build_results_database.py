import csv
import gzip
import hashlib
import importlib.util
import io
import json
import tarfile
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from analysis import build_results_database as database


def json_bytes(payload):
    return (json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8")


def jsonl_gzip(records):
    output = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=output, mtime=0) as compressed:
        for record in records:
            compressed.write(json_bytes(record))
    return output.getvalue()


def add_bytes(archive, name, payload):
    info = tarfile.TarInfo(name)
    info.size = len(payload)
    archive.addfile(info, io.BytesIO(payload))


def create_run(
    campaign_root: Path,
    run_id: str,
    job_id: str,
    selection: str,
    *,
    repeat: int = 1,
    fitness_offset: float = 0.0,
) -> Path:
    archive_path = (
        campaign_root
        / "runs"
        / "test_problem"
        / f"repeat-{repeat}"
        / f"run_{job_id}.tar.gz"
    )
    archive_path.parent.mkdir(parents=True)
    root = f"run_{job_id}"
    adjacency = {
        "0": [1, 3],
        "1": [0, 2],
        "2": [1, 3],
        "3": [2, 0],
    }
    adjacency_sha256 = hashlib.sha256(
        json.dumps(adjacency, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    topology_parameters = {"family": "test-ring", "nodes": 4}
    topology_payload = {
        "schema_version": 2,
        "name": "torus",
        "islands": 4,
        "torus_shape": [2, 2],
        "parameters": topology_parameters,
        "adjacency": adjacency,
        "graph_metrics": {"adjacency_sha256": adjacency_sha256},
        "note": "test topology",
    }
    metadata = {
        "schema_version": 1,
        "run_id": run_id,
        "experiment_key": f"experiment-{selection}",
        "status": "complete",
        "started_utc": "2026-01-01T00:00:00+00:00",
        "completed_utc": "2026-01-01T00:01:00+00:00",
        "islands_completed": 4,
        "scientific_configuration": {
            "benchmark": {
                "name": "r99_test_problem",
                "dimension": 2,
                "objective_direction": "minimize",
                "optimum_value": 0.0,
                "cec_function_id": 99,
            },
            "dimension": 2,
            "islands": 4,
            "evaluations_per_island": 4,
            "population": 2,
            "offspring": 1,
            "migration": {
                "group_size": 1,
                "interval": 1,
                "interval_unit": "evaluation-count difference",
                "selection": selection,
                "acceptance": "plain",
            },
            "topology": {
                "name": "torus",
                "parameters": topology_parameters,
                "adjacency_sha256": adjacency_sha256,
            },
            "repeat": repeat,
            "seed": {"repeat_base": 123},
            "metrics": {"profile": "research-v1-full-buffered"},
        },
        "resources": {"slurm": {"SLURM_JOB_ID": job_id}},
        "provenance": {"git_commit": "deadbeef"},
    }
    contract = {
        "schema_version": 1,
        "delay_definition": "source_step - process_step (negative means stale/older)",
    }
    with tarfile.open(archive_path, "w:gz") as archive:
        add_bytes(archive, f"{root}/metadata.json", json_bytes(metadata))
        add_bytes(
            archive,
            f"{root}/results/topology.json",
            json_bytes(topology_payload),
        )
        add_bytes(
            archive,
            f"{root}/metrics/data_contract.json",
            json_bytes(contract),
        )
        for island in range(4):
            final_fitness = float(island + 1) + fitness_offset
            directory = f"{root}/metrics/island_{island:03d}"
            add_bytes(
                archive,
                f"{directory}/final_solution.json",
                json_bytes(
                    {
                        "run_id": run_id,
                        "island": island,
                        "objectives": [final_fitness],
                    }
                ),
            )
            histories = [
                {
                    "phase": "initial_population",
                    "step": 0,
                    "evaluations": 2,
                    "best_so_far": final_fitness + 2,
                    "current_best": final_fitness + 2,
                    "population_mean": final_fitness + 3,
                    "population_median": final_fitness + 3,
                    "population_worst": final_fitness + 4,
                    "timestamp_unix": 100.0,
                    "elapsed_since_migration_measurement_start_seconds": None,
                },
                {
                    "phase": "after_replacement",
                    "step": 1,
                    "evaluations": 3,
                    "best_so_far": final_fitness + 1,
                    "current_best": final_fitness + 1,
                    "population_mean": final_fitness + 2,
                    "population_median": final_fitness + 2,
                    "population_worst": final_fitness + 3,
                    "timestamp_unix": 101.0,
                    "elapsed_since_migration_measurement_start_seconds": 1.0,
                },
                {
                    "phase": "after_replacement",
                    "step": 2,
                    "evaluations": 4,
                    "best_so_far": final_fitness,
                    "current_best": final_fitness,
                    "population_mean": final_fitness + 1,
                    "population_median": final_fitness + 1,
                    "population_worst": final_fitness + 2,
                    "timestamp_unix": 102.0,
                    "elapsed_since_migration_measurement_start_seconds": 2.0,
                },
            ]
            add_bytes(
                archive,
                f"{directory}/fitness_history.jsonl.gz",
                jsonl_gzip(histories),
            )
            events = [
                {
                    "record_type": "send",
                    "event_id": f"{island}:1",
                    "source_island": island,
                    "destination_island": (island + 1) % 4,
                },
                {
                    "record_type": "process",
                    "event_id": f"{(island - 1) % 4}:1",
                    "source_island": (island - 1) % 4,
                    "destination_island": island,
                    "processed": True,
                    "process_status": "accepted",
                    "source_step": 1,
                    "process_step": 2,
                    "signed_delay_steps": -(island + 1),
                    "process_timestamp_unix": 102.0 + island,
                    "accepted_by_filter": True,
                    "survived_replacement": island % 2 == 0,
                },
                {
                    "record_type": "process",
                    "event_id": f"{(island - 1) % 4}:2",
                    "source_island": (island - 1) % 4,
                    "destination_island": island,
                    "processed": False,
                    "process_status": "queued_not_dequeued_at_end_of_run",
                    "signed_delay_steps": None,
                },
            ]
            add_bytes(
                archive,
                f"{directory}/migration_events.jsonl.gz",
                jsonl_gzip(events),
            )
            add_bytes(
                archive,
                f"{directory}/runtime.json",
                json_bytes(
                    {
                        "island": island,
                        "actual_evaluations": 4,
                        "actual_steps": 2,
                        "algorithm_wall_seconds": 2.0,
                        "queue": {
                            "maximum_queue_depth": 2,
                            "queue_depth_at_query": 1,
                        },
                    }
                ),
            )
            add_bytes(
                archive,
                f"{directory}/summary.json",
                json_bytes(
                    {
                        "island": island,
                        "sent_event_records": 1,
                        "process_event_records": 2,
                        "prefetched_unprocessed_event_records": 0,
                        "queued_unprocessed_event_records": 1,
                        "counters": {"received_before_filter": 1},
                    }
                ),
            )
    checksum = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    Path(f"{archive_path}.sha256").write_text(
        f"{checksum}  {archive_path.name}\n", encoding="utf-8"
    )
    return archive_path


def read_csv(path):
    with path.open("r", encoding="utf-8", newline="") as source:
        return list(csv.DictReader(source))


class ResultsDatabaseTests(unittest.TestCase):
    def test_all_benchmark_delay_plots_use_worker_threads(self):
        with tempfile.TemporaryDirectory() as temporary_text:
            temporary = Path(temporary_text)
            database_root = temporary / "analysis_database"
            database_root.mkdir()
            destination = temporary / "outputs"
            barrier = threading.Barrier(2)
            thread_ids: set[int] = set()
            thread_ids_lock = threading.Lock()

            def fake_generate_delay_pattern_plots(**kwargs):
                with thread_ids_lock:
                    thread_ids.add(threading.get_ident())
                barrier.wait(timeout=5)
                return {"png_files": [f"{kwargs['benchmark']}.png"]}

            with mock.patch.object(
                database,
                "delay_benchmarks",
                return_value=["benchmark_a", "benchmark_b"],
            ), mock.patch(
                "analysis.delay_pattern_plots.generate_delay_pattern_plots",
                side_effect=fake_generate_delay_pattern_plots,
            ):
                result = database.main(
                    [
                        "--output",
                        str(database_root),
                        "--plot-delay-patterns-all",
                        "--pattern-output",
                        str(destination),
                        "--workers",
                        "2",
                    ]
                )

            self.assertEqual(0, result)
            self.assertEqual(2, len(thread_ids))

    def test_incremental_ingestion_is_idempotent_and_appends_campaign(self):
        with tempfile.TemporaryDirectory() as temporary_text:
            temporary = Path(temporary_text)
            best = temporary / "torus_best"
            random = temporary / "torus_random"
            output = temporary / "database"
            processing = output / ".processing"
            create_run(best, "run-best", "100", "best")
            create_run(
                best,
                "run-best-repeat-2",
                "101",
                "best",
                repeat=2,
                fitness_offset=2.0,
            )
            create_run(random, "run-random", "200", "random")

            arguments = [
                str(best),
                "--output",
                str(output),
                "--rank-count",
                "1",
                "--workers",
                "2",
            ]
            self.assertEqual(0, database.main(arguments))
            self.assertEqual(0, database.main(arguments))
            self.assertEqual(2, len(read_csv(processing / "runs.csv")))
            self.assertFalse((output / "run.csv").exists())

            self.assertEqual(
                0,
                database.main(
                    [
                        str(random),
                        "--output",
                        str(output),
                        "--rank-count",
                        "1",
                        "--workers",
                        "2",
                    ]
                ),
            )
            run_rows = read_csv(processing / "runs.csv")
            self.assertEqual(3, len(run_rows))
            self.assertEqual({"torus_best", "torus_random"}, {row["campaign"] for row in run_rows})
            self.assertEqual(12, len(read_csv(processing / "islands.csv")))
            self.assertEqual(9, len(read_csv(processing / "run_convergence.csv")))
            delay_rows = read_csv(processing / "delay_summary.csv")
            self.assertEqual(6, len(delay_rows))
            self.assertEqual({"top_1", "bottom_1"}, {row["rank_group"] for row in delay_rows})

            configuration_rows = read_csv(processing / "configuration_summary.csv")
            self.assertEqual(2, len(configuration_rows))
            best_configuration = next(
                row for row in configuration_rows if row["migrant_selection"] == "best"
            )
            self.assertEqual("2", best_configuration["repeat_count"])
            self.assertEqual("1;2", best_configuration["repeats"])
            self.assertEqual(
                2.0,
                float(best_configuration["final_island_fitness_best_repeat_mean"]),
            )
            self.assertEqual(6, len(read_csv(processing / "configuration_convergence.csv")))
            self.assertEqual(4, len(read_csv(processing / "configuration_delay_summary.csv")))
            self.assertEqual(1, len(read_csv(processing / "topologies.csv")))
            self.assertEqual(3, len(read_csv(processing / "topology_runs.csv")))
            self.assertEqual(1, len(list((output / "topologies").glob("*.json"))))

            fitness_tables = temporary / "outputs"
            self.assertEqual(
                0,
                database.main(
                    [
                        "--output",
                        str(output),
                        "--export-fitness-table",
                        "--fitness-table-output",
                        str(fitness_tables),
                    ]
                ),
            )
            fitness_rows = read_csv(
                fitness_tables / "r99_test_problem" / "fitness_summary.csv"
            )
            self.assertEqual(2, len(fitness_rows))
            self.assertTrue(
                {"run_id", "job_id", "experiment_key", "campaign", "repeat"}.isdisjoint(
                    fitness_rows[0]
                )
            )
            best_fitness_row = next(
                row for row in fitness_rows if row["migrant_selection"] == "best"
            )
            self.assertEqual("2", best_fitness_row["repeats_averaged"])
            self.assertEqual(
                "", best_fitness_row["mean_best_fitness_at_25pct_evaluations"]
            )
            self.assertEqual(
                4.0,
                float(best_fitness_row["mean_best_fitness_at_50pct_evaluations"]),
            )
            self.assertEqual(
                3.0,
                float(best_fitness_row["mean_best_fitness_at_75pct_evaluations"]),
            )
            self.assertEqual(
                2.0,
                float(best_fitness_row["mean_best_fitness_at_100pct_evaluations"]),
            )
            self.assertEqual(2.0, float(best_fitness_row["mean_final_fitness"]))
            self.assertEqual(
                3.0,
                float(
                    best_fitness_row[
                        "mean_evaluations_to_50pct_observed_improvement"
                    ]
                ),
            )
            self.assertEqual(
                4.0,
                float(
                    best_fitness_row[
                        "mean_evaluations_to_90pct_observed_improvement"
                    ]
                ),
            )

            # Simulate a database created before topology collection existed,
            # then backfill it without rebuilding the large convergence tables.
            for source_path in (processing / "runs").glob("*/source.json"):
                source_record = json.loads(source_path.read_text(encoding="utf-8"))
                source_record.pop("topology", None)
                source_path.write_text(
                    json.dumps(source_record, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
            for topology_path in (output / "topologies").glob("*.json"):
                topology_path.unlink()
            self.assertEqual(
                0,
                database.main(
                    [
                        str(temporary),
                        "--output",
                        str(output),
                        "--rank-count",
                        "1",
                        "--workers",
                        "2",
                        "--collect-topologies-only",
                    ]
                ),
            )
            self.assertEqual(1, len(read_csv(processing / "topologies.csv")))
            self.assertEqual(3, len(read_csv(processing / "topology_runs.csv")))
            self.assertEqual(1, len(list((output / "topologies").glob("*.json"))))

            for run_directory in (processing / "runs").iterdir():
                with gzip.open(
                    run_directory / "island_convergence.csv.gz",
                    "rt",
                    encoding="utf-8",
                    newline="",
                ) as source:
                    self.assertEqual(12, len(list(csv.DictReader(source))))
                with gzip.open(
                    run_directory / "top_bottom_delay_events.csv.gz",
                    "rt",
                    encoding="utf-8",
                    newline="",
                ) as source:
                    events = list(csv.DictReader(source))
                self.assertEqual(4, len(events))
                self.assertEqual(2, sum(row["processed"] == "False" for row in events))
                self.assertTrue(
                    all(not row["signed_delay_steps"] for row in events if row["processed"] == "False")
                )

            manifest = json.loads((output / "database_manifest.json").read_text())
            self.assertEqual(3, manifest["run_count"])
            self.assertEqual(2, manifest["view_rebuild_workers"])
            self.assertEqual(36, manifest["sharded_row_counts"]["island_convergence"])
            self.assertEqual(12, manifest["sharded_row_counts"]["top_bottom_delay_events"])
            self.assertEqual(
                {
                    "topology_count": 1,
                    "covered_run_count": 3,
                    "missing_run_count": 0,
                    "complete": True,
                    "missing_run_ids": [],
                },
                manifest["topology_inventory"],
            )
            self.assertEqual(
                {
                    "configuration_summary": 2,
                    "configuration_convergence": 6,
                    "configuration_delay_summary": 4,
                },
                manifest["configuration_row_counts"],
            )
            deterministic_tables = (
                "runs.csv",
                "islands.csv",
                "run_convergence.csv",
                "delay_summary.csv",
                "configuration_summary.csv",
                "configuration_convergence.csv",
                "configuration_delay_summary.csv",
                "topologies.csv",
                "topology_runs.csv",
            )
            parallel_bytes = {
                name: (processing / name).read_bytes() for name in deterministic_tables
            }
            self.assertEqual(
                0,
                database.main(
                    [
                        "--output",
                        str(output),
                        "--rank-count",
                        "1",
                        "--workers",
                        "1",
                        "--rebuild-views-only",
                    ]
                ),
            )
            sequential_bytes = {
                name: (processing / name).read_bytes() for name in deterministic_tables
            }
            self.assertEqual(parallel_bytes, sequential_bytes)
            self.assertEqual(
                0,
                database.main(
                    [
                        "--output",
                        str(output),
                        "--rank-count",
                        "1",
                        "--workers",
                        "3",
                        "--rebuild-views-only",
                    ]
                ),
            )
            multithreaded_bytes = {
                name: (processing / name).read_bytes() for name in deterministic_tables
            }
            self.assertEqual(sequential_bytes, multithreaded_bytes)

            if any(
                importlib.util.find_spec(package) is None
                for package in ("matplotlib", "numpy", "sklearn")
            ):
                return

            from analysis.delay_pattern_plots import generate_delay_pattern_plots
            from analysis.fitness_comparison_plots import (
                generate_all_fitness_comparison_plots,
                generate_fitness_comparison_plots,
            )

            delay_output = output / "test_delay_plots"
            delay_output.mkdir()
            (delay_output / "fitness_summary.csv").write_text(
                "mean_final_fitness\n1.0\n", encoding="utf-8"
            )
            (delay_output / "combined").mkdir()
            (delay_output / "combined" / "fitness.png").write_bytes(b"fitness")
            for legacy_delay_artifact in (
                "cluster_summary.csv",
                "curve_assignments.csv",
                "configuration_pattern_frequency.csv",
                "pattern_manifest.json",
            ):
                (delay_output / legacy_delay_artifact).write_text(
                    "legacy\n", encoding="utf-8"
                )
            delay_manifest = generate_delay_pattern_plots(
                database=output,
                destination=delay_output,
                selected_patterns=1,
                candidate_clusters=1,
                bins=10,
                smoothing=1,
                progress=lambda _message: None,
            )
            self.assertIsNone(delay_manifest["benchmark_filter"])
            self.assertIsNone(delay_manifest["run_filter"])
            self.assertEqual(4, len(delay_manifest["png_files"]))
            self.assertEqual(3, delay_manifest["groups"]["top_1"]["curve_count"])
            self.assertEqual(3, delay_manifest["groups"]["top_1"]["run_count"])
            self.assertEqual(
                [1], delay_manifest["groups"]["top_1"]["curves_per_run_values"]
            )
            self.assertTrue((delay_output / "combined" / "fitness.png").is_file())
            self.assertTrue((delay_output / "fitness_summary.csv").is_file())
            self.assertFalse((delay_output / "README.md").exists())
            self.assertTrue((delay_output / "top_1" / "pca_clusters.png").is_file())
            self.assertTrue(
                (delay_output / "bottom_1" / "pca_clusters.png").is_file()
            )
            for unwanted in (
                "cluster_summary.csv",
                "curve_assignments.csv",
                "configuration_pattern_frequency.csv",
                "pattern_manifest.json",
            ):
                self.assertFalse((delay_output / unwanted).exists())

            all_delay_output = temporary / "all_delay_outputs"
            self.assertEqual(
                0,
                database.main(
                    [
                        "--output",
                        str(output),
                        "--plot-delay-patterns-all",
                        "--pattern-output",
                        str(all_delay_output),
                        "--patterns-per-group",
                        "1",
                        "--pattern-clusters",
                        "1",
                        "--pattern-bins",
                        "10",
                        "--pattern-smoothing",
                        "1",
                    ]
                ),
            )
            benchmark_delay_output = all_delay_output / "r99_test_problem"
            self.assertTrue(
                (benchmark_delay_output / "top_1" / "pattern_01.png").is_file()
            )
            self.assertTrue(
                (benchmark_delay_output / "bottom_1" / "pattern_01.png").is_file()
            )
            self.assertTrue(
                (benchmark_delay_output / "top_1" / "pca_clusters.png").is_file()
            )
            self.assertTrue(
                (benchmark_delay_output / "bottom_1" / "pca_clusters.png").is_file()
            )
            for unwanted in (
                "cluster_summary.csv",
                "curve_assignments.csv",
                "configuration_pattern_frequency.csv",
                "pattern_manifest.json",
            ):
                self.assertFalse((benchmark_delay_output / unwanted).exists())

            run_delay_output = temporary / "run_delay_output"
            self.assertEqual(
                0,
                database.main(
                    [
                        "--output",
                        str(output),
                        "--plot-delay-patterns",
                        "--pattern-run",
                        "run-best",
                        "--pattern-output",
                        str(run_delay_output),
                        "--patterns-per-group",
                        "1",
                        "--pattern-clusters",
                        "1",
                        "--pattern-bins",
                        "10",
                        "--pattern-smoothing",
                        "1",
                    ]
                ),
            )
            self.assertTrue(
                (run_delay_output / "top_1" / "pca_clusters.png").is_file()
            )
            self.assertTrue(
                (run_delay_output / "bottom_1" / "pca_clusters.png").is_file()
            )

            fitness_output = output / "test_fitness_plots"
            fitness_output.mkdir()
            (fitness_output / "fitness_summary.csv").write_text(
                "mean_final_fitness\n1.0\n", encoding="utf-8"
            )
            fitness_manifest = generate_fitness_comparison_plots(
                database=output,
                destination=fitness_output,
                benchmark="r99_test_problem",
                group_by="both",
                progress=lambda _message: None,
            )
            self.assertEqual(3, len(fitness_manifest["png_files"]))
            self.assertTrue(
                (fitness_output / "by_strategy" / "strategy_best.png").is_file()
            )
            self.assertTrue(
                (fitness_output / "by_topology" / "topology_torus.png").is_file()
            )
            self.assertEqual(
                "mean_final_fitness\n1.0\n",
                (fitness_output / "fitness_summary.csv").read_text(encoding="utf-8"),
            )
            for unwanted in (
                "fitness_manifest.json",
                "comparison_contexts.csv",
                "fitness_plot_series.csv",
                "README.md",
            ):
                self.assertFalse((fitness_output / unwanted).exists())

            combined_output = output / "test_fitness_combined"
            combined_manifest = generate_fitness_comparison_plots(
                database=output,
                destination=combined_output,
                benchmark="r99_test_problem",
                group_by="combined",
                progress=lambda _message: None,
            )
            self.assertEqual(
                ["combined/all_topology_strategy_configurations.png"],
                combined_manifest["png_files"],
            )
            self.assertTrue(
                (
                    combined_output
                    / "combined"
                    / "all_topology_strategy_configurations.png"
                ).is_file()
            )

            all_output = output / "test_fitness_all"
            images_output = output / "test_fitness_images_only"
            all_manifest = generate_all_fitness_comparison_plots(
                database=output,
                destination=all_output,
                group_by="combined",
                images_destination=images_output,
                progress=lambda _message: None,
            )
            self.assertEqual(1, all_manifest["benchmark_count"])
            self.assertEqual(1, all_manifest["png_count"])
            self.assertEqual(["r99_test_problem"], list(all_manifest["benchmarks"]))
            self.assertTrue(
                (
                    all_output
                    / "r99_test_problem"
                    / "combined"
                    / "all_topology_strategy_configurations.png"
                ).is_file()
            )
            copied_files = sorted(
                path.relative_to(images_output)
                for path in images_output.rglob("*")
                if path.is_file()
            )
            self.assertEqual(
                [
                    Path(
                        "r99_test_problem/combined/"
                        "all_topology_strategy_configurations.png"
                    )
                ],
                copied_files,
            )

    def test_convergence_and_signed_delay_definitions(self):
        speed = database.convergence_metrics(
            [(2, 10.0), (3, 7.0), (4, 5.0)], "minimize"
        )
        self.assertEqual(5.0, speed["observed_improvement"])
        self.assertEqual(3, speed["eval_at_50pct"])
        self.assertEqual(4, speed["eval_at_final"])
        self.assertAlmostEqual(0.55, speed["improvement_auc"])

        delays = database.delay_description([-12, -2, 0, 3], 10)
        self.assertEqual(2, delays["delayed_count"])
        self.assertEqual(1, delays["aligned_count"])
        self.assertEqual(1, delays["accelerated_count"])
        self.assertEqual(1, delays["strongly_delayed_count"])

    def test_legacy_database_files_move_under_processing(self):
        with tempfile.TemporaryDirectory() as temporary_text:
            database_root = Path(temporary_text) / "analysis_database"
            (database_root / "runs" / "run-a").mkdir(parents=True)
            (database_root / "runs" / "run-a" / "run.csv").write_text(
                "run_id\nrun-a\n", encoding="utf-8"
            )
            (database_root / "runs.csv").write_text(
                "run_id\nrun-a\n", encoding="utf-8"
            )
            (database_root / "database_manifest.json").write_text(
                "{}\n", encoding="utf-8"
            )

            processing = database.migrate_legacy_processing_layout(database_root)

            self.assertEqual(database_root / ".processing", processing)
            self.assertTrue((processing / "runs" / "run-a" / "run.csv").is_file())
            self.assertTrue((processing / "runs.csv").is_file())
            self.assertTrue((database_root / "database_manifest.json").is_file())
            self.assertFalse((database_root / "runs").exists())
            self.assertFalse((database_root / "runs.csv").exists())


if __name__ == "__main__":
    unittest.main()
