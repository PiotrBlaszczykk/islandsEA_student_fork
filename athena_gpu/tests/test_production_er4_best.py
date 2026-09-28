"""Pure contract checks for the 120-job ER4/best Athena production map."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from athena_gpu.campaign_er4_best import plan_document, record_task, task_matrix, validate_plan
from athena_gpu.tests.campaign_fixture import create_campaign
from athena_gpu.production_er4_best import (
    TASK_COUNT,
    check_contract,
    configuration,
)
from athena_gpu.validate_study_run import _check_er4_topology, _spec
from islands_desync.geneticAlgorithm.utils.benchmarks_refined import BENCHMARKS
from islands_desync.islands.topologies.fixed_graph import graph_parameters, load_graph


class ProductionER4BestTests(unittest.TestCase):
    def test_exact_order_and_coverage(self):
        check_contract()
        mapped = [configuration(task) for task in range(1, TASK_COUNT + 1)]
        self.assertEqual([(name, repeat) for name in BENCHMARKS for repeat in (1, 2, 3)], mapped)
        self.assertEqual(120, len(set(mapped)))
        self.assertEqual((BENCHMARKS[0], 1), configuration(1))
        self.assertEqual((BENCHMARKS[-1], 3), configuration(120))
        for invalid in (0, 121):
            with self.assertRaises(ValueError):
                configuration(invalid)

    def test_full_er4_spec_keeps_approved_scientific_budget(self):
        spec = _spec("full", 3, BENCHMARKS[-1], "er4")
        self.assertEqual(BENCHMARKS[-1], spec["benchmark"])
        self.assertEqual(200, spec["dimension"])
        self.assertEqual(144, spec["islands"])
        self.assertEqual(8000, spec["evaluations_per_island"])
        self.assertEqual(22260912, spec["repeat_seed"])
        self.assertEqual("best", spec["migrant_selection"])
        self.assertIsNone(spec["torus_rows"])

    def test_validator_rejects_altered_er4_adjacency(self):
        document = load_graph("er4")
        topology = {
            "schema_version": 2,
            "name": "er4",
            "islands": 144,
            "torus_shape": None,
            "parameters": graph_parameters("er4"),
            "adjacency": copy.deepcopy(document["adjacency"]),
            "graph_metrics": {
                "adjacency_sha256": document["provenance"]["adjacency_sha256"],
                "node_count": 144,
                "weakly_connected": True,
                "strongly_connected": True,
            },
        }
        spec = _spec("full", 1, BENCHMARKS[0], "er4")
        errors = []
        _check_er4_topology(topology, spec, errors)
        self.assertEqual([], errors)
        topology["adjacency"]["0"].pop()
        _check_er4_topology(topology, spec, errors)
        self.assertIn("saved ER4 adjacency differs", errors)

    def test_campaign_plan_matches_the_ares_style_task_matrix(self):
        plan = plan_document("123", "a" * 40)
        self.assertEqual("islandsea-er4-best-athena-campaign-v1", plan["schema"])
        self.assertEqual(120, plan["task_count"])
        self.assertEqual(task_matrix(), plan["tasks"])
        self.assertEqual("best", plan["configuration"]["migration"]["selection"])
        self.assertEqual(200, plan["configuration"]["dimension"])
        self.assertEqual(
            "469cc283543dcc60d5bf8f07db2eabfb12cab34637f4a6d26bca51d07f85cccc",
            plan["configuration"]["topology"]["adjacency_sha256"],
        )

    def test_random_plan_changes_only_selection_and_campaign_identity(self):
        best = plan_document("123", "a" * 40)
        random = plan_document("124", "a" * 40, "random")
        self.assertEqual("er4_random", random["campaign"])
        self.assertEqual("islandsea-er4-random-athena-campaign-v1", random["schema"])
        self.assertEqual("random", random["configuration"]["migration"]["selection"])
        self.assertEqual(best["tasks"], random["tasks"])
        for key in ("dimension", "islands", "evaluations_per_island", "population",
                    "offspring", "topology", "base_seed", "benchmark_instance_seed"):
            self.assertEqual(best["configuration"][key], random["configuration"][key])
        self.assertEqual(_spec("full", 3, BENCHMARKS[-1], "er4", "random")["migrant_selection"],
                         "random")
        validate_plan(random, "124", "random")
        with self.assertRaises(ValueError):
            validate_plan(random, "124", "best")

    def test_campaign_record_indexes_one_verified_portable_bundle(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            campaign = root / "er4_best_123"
            campaign.mkdir()
            (campaign / "campaign_plan.json").write_text(
                json.dumps(plan_document("123", "a" * 40)), encoding="utf-8"
            )
            run_dir = root / "results" / "456"
            run_dir.mkdir(parents=True)
            raw = root / "raw"
            raw.mkdir()
            task = task_matrix()[0]
            (run_dir / "validation.json").write_text(json.dumps({
                "status": "passed", "valid": True, "mode": "full",
                "benchmark": task["benchmark"], "dimension": 200,
                "topology": "er4", "migrant_selection": "best",
                "migrant_acceptance": "plain", "repeat": 1,
                "base_seed": 20260912, "repeat_seed": 20260912,
                "git_commit": "b" * 40,
            }), encoding="utf-8")
            (run_dir / "result_pointer.json").write_text(
                json.dumps({"run_directory": str(raw)}), encoding="utf-8"
            )
            plan = plan_document("123", "a" * 40)
            (raw / "run_metadata.json").write_text(json.dumps({
                "scientific_configuration": {
                    "benchmark": {"name": task["benchmark"]},
                    "dimension": 200, "islands": 144,
                    "evaluations_per_island": 8000,
                    "population": 16, "offspring": 4, "repeat": 1,
                    "migration": plan["configuration"]["migration"],
                    "topology": plan["configuration"]["topology"],
                    "seed": {
                        "requested_base": 20260912,
                        "repeat_base": 20260912,
                        "benchmark_instance_seed": 20260511,
                    },
                    "metrics": {"profile": "research-v1-full-buffered"},
                },
                "resources": {"slurm": {
                    "SLURM_JOB_ID": "456", "SLURM_ARRAY_JOB_ID": "123",
                    "SLURM_ARRAY_TASK_ID": "1",
                }},
                "provenance": {"git_commit": "b" * 40},
            }), encoding="utf-8")
            archive = root / "exports" / "run_456.tar.gz"
            archive.parent.mkdir()
            archive.write_bytes(b"synthetic archive")
            digest = hashlib.sha256(archive.read_bytes()).hexdigest()
            (archive.parent / (archive.name + ".sha256")).write_text(
                f"{digest}  {archive.name}\n", encoding="ascii"
            )
            with patch("athena_gpu.campaign_er4_best.verify_archive", return_value={
                "job_id": "456", "complete": True, "validation": "passed",
            }):
                record = record_task(campaign, "123", 1, "456", run_dir, archive)
            self.assertEqual(digest, record["archive_sha256"])
            self.assertEqual(
                archive.read_bytes(),
                (campaign / record["archive"]).read_bytes(),
            )
            self.assertTrue((campaign / "tasks" / "task-001.json").is_file())

    def test_random_record_accepts_random_and_rejects_best_validation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = create_campaign(root, strategy="random")
            campaign, plan = fixture["campaign"], fixture["plan"]
            task = plan["tasks"][0]
            record = campaign / "tasks/task-001.json"
            record.unlink()
            old_bundle = campaign / "runs/r01_elliptic/repeat-1/run_501.tar.gz"
            old_checksum = old_bundle.with_name(old_bundle.name + ".sha256")
            archive = root / "exports/run_501.tar.gz"
            archive.parent.mkdir()
            archive.write_bytes(old_bundle.read_bytes())
            archive.with_name(archive.name + ".sha256").write_bytes(old_checksum.read_bytes())
            old_bundle.unlink()
            old_checksum.unlink()
            old_bundle.parent.rmdir()
            run_dir = fixture["results"] / "501"
            raw = root / "raw"
            raw.mkdir()
            (run_dir / "result_pointer.json").write_text(
                json.dumps({"run_directory": str(raw)}), encoding="utf-8")
            (raw / "run_metadata.json").write_text(json.dumps({
                "scientific_configuration": {
                    "benchmark": {"name": task["benchmark"]},
                    "dimension": 200, "islands": 144, "evaluations_per_island": 8000,
                    "population": 16, "offspring": 4, "repeat": 1,
                    "migration": plan["configuration"]["migration"],
                    "topology": plan["configuration"]["topology"],
                    "seed": {"requested_base": 20260912, "repeat_base": 20260912,
                             "benchmark_instance_seed": 20260511},
                    "metrics": {"profile": "research-v1-full-buffered"},
                },
                "resources": {"slurm": {"SLURM_JOB_ID": "501",
                                        "SLURM_ARRAY_JOB_ID": "123",
                                        "SLURM_ARRAY_TASK_ID": "1"}},
                "provenance": {"git_commit": "b" * 40},
            }), encoding="utf-8")
            validation_path = run_dir / "validation.json"
            validation = json.loads(validation_path.read_text(encoding="utf-8"))
            validation["migrant_selection"] = "best"
            validation_path.write_text(json.dumps(validation), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "migrant_selection"):
                record_task(campaign, "123", 1, "501", run_dir, archive, "random")
            validation["migrant_selection"] = "random"
            validation_path.write_text(json.dumps(validation), encoding="utf-8")
            with patch("athena_gpu.campaign_er4_best.verify_archive", return_value={
                "job_id": "501", "complete": True, "validation": "passed",
            }):
                made = record_task(campaign, "123", 1, "501", run_dir, archive, "random")
            self.assertEqual("random", made["migrant_selection"])
            self.assertEqual("islandsea-er4-random-athena-campaign-v1", made["schema"])
            self.assertEqual(archive.read_bytes(), (campaign / made["archive"]).read_bytes())


if __name__ == "__main__":
    unittest.main()
