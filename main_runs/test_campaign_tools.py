import ast
import copy
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import tarfile
import tempfile
import unittest


MODULE_PATH = Path(__file__).with_name("campaign_tools.py")
SPEC = importlib.util.spec_from_file_location("campaign_tools", MODULE_PATH)
campaign = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(campaign)


class CampaignToolsTests(unittest.TestCase):
    def test_batch_scripts_use_absolute_project_path_without_nested_submit(self):
        for filename in ("run_torus_best_array.sh", "finalize_torus_best.sh"):
            script = MODULE_PATH.with_name(filename).read_text(encoding="utf-8")
            self.assertIn('ISLANDS_PROJECT_DIR', script)
            self.assertIn('ISLANDS_CAMPAIGN_DIR', script)
            self.assertNotIn('BASH_SOURCE', script)
            self.assertNotIn('sbatch ', script)
        launcher = MODULE_PATH.with_name("launch_torus_best.sh").read_text(encoding="utf-8")
        self.assertIn('--array="1-120%${MAX_PARALLEL}"', launcher)
        self.assertIn('--dependency="afterany:${ARRAY_JOB_ID}"', launcher)

    @staticmethod
    def metadata(task, array_job_id, job_id):
        return {
            "status": "complete", "run_id": f"run-{task['task_id']}",
            "experiment_key": f"key-{task['benchmark']}",
            "scientific_configuration": {
                "benchmark": {"name": task["benchmark"], "implementation_sha256": "b" * 64}, "dimension": 200,
                "islands": 144, "evaluations_per_island": 8000,
                "population": 16, "offspring": 4, "repeat": task["repeat"],
                "migration": {"group_size": 5, "interval": 5,
                              "interval_unit": "evaluation-count difference",
                              "selection": "best", "acceptance": "plain"},
                "topology": {"name": "torus", "parameters": {"rows": 12, "columns": 12},
                             "adjacency_sha256": "t" * 64},
                "seed": {"requested_base": 20260912, "repeat_base": task["repeat_seed"]},
                "metrics": {"profile": "research-v1-full-buffered"},
            },
            "resources": {"required_ray_cpus": 289, "required_slurm_cpus": 290,
                          "slurm": {"SLURM_JOB_ID": str(job_id),
                                    "SLURM_ARRAY_JOB_ID": str(array_job_id),
                                    "SLURM_ARRAY_TASK_ID": str(task["task_id"]),
                                    "SLURM_JOB_NUM_NODES": "7",
                                    "SLURM_JOB_ACCOUNT": "plglscclass26-cpu",
                                    "SLURM_JOB_PARTITION": "plgrid",
                                    "ISLANDS_ALLOCATED_CPUS_PER_NODE": "48"}},
            "provenance": {"git_dirty": False, "runtime_sha256": "r" * 64},
        }

    def test_exact_40_by_3_matrix(self):
        tasks = campaign.task_matrix()
        self.assertEqual(40, len(campaign.BENCHMARKS))
        self.assertEqual(120, len(tasks))
        self.assertEqual(list(range(1, 121)), [task["task_id"] for task in tasks])
        for benchmark in campaign.BENCHMARKS:
            selected = [task for task in tasks if task["benchmark"] == benchmark]
            self.assertEqual([1, 2, 3], [task["repeat"] for task in selected])
            self.assertEqual([20260912, 21260912, 22260912], [task["repeat_seed"] for task in selected])
            self.assertEqual({200}, {task["dimension"] for task in selected})

    def test_frozen_names_match_the_runtime_registry_source(self):
        package = MODULE_PATH.parents[1] / "islands_desync/islands_desync/geneticAlgorithm/utils/benchmarks_refined"

        def literal_assignment(path, name):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in tree.body:
                if isinstance(node, ast.Assign) and any(
                    isinstance(target, ast.Name) and target.id == name for target in node.targets
                ):
                    return ast.literal_eval(node.value)
            self.fail(f"{name} missing from {path}")

        suffixes = literal_assignment(package / "__init__.py", "_CEC_SUFFIXES")
        discrete = literal_assignment(package / "discrete.py", "DISCRETE_BENCHMARKS")
        continuous = tuple(f"r{index:02d}_{suffix}" for index, suffix in enumerate(suffixes, 1))
        self.assertEqual(campaign.CONTINUOUS, continuous)
        self.assertEqual(campaign.BINARY, discrete)

    def test_plan_is_frozen_and_indexed(self):
        plan = campaign.expected_plan("a" * 40)
        campaign.validate_plan(plan)
        self.assertEqual("r01_elliptic", campaign.task_for(plan, 1)["benchmark"])
        self.assertEqual(3, campaign.task_for(plan, 3)["repeat"])
        self.assertEqual("b10_maxcut_ring", campaign.task_for(plan, 120)["benchmark"])
        broken = copy.deepcopy(plan)
        broken["configuration"]["topology"]["name"] = "complete"
        with self.assertRaises(ValueError):
            campaign.validate_plan(broken)

    def test_metadata_contract_rejects_scientific_drift(self):
        task = campaign.task_matrix()[0]
        metadata = self.metadata(task, "9000", "9001")
        self.assertEqual([], campaign.validate_metadata(metadata, task, "9000", "9001"))
        metadata["scientific_configuration"]["migration"]["selection"] = "random"
        self.assertIn("migration selection mismatch", campaign.validate_metadata(metadata, task, "9000", "9001"))

    def test_finalizer_requires_and_packages_all_120_runs(self):
        with tempfile.TemporaryDirectory(prefix="torus-best-test-") as temporary:
            root = Path(temporary)
            plan = campaign.expected_plan("a" * 40)
            campaign.write_json(root / "campaign_plan.json", plan)
            for task in plan["tasks"]:
                job_id = 100000 + task["task_id"]
                archive = root / "runs" / f"run_{job_id}.tar.gz"
                archive.parent.mkdir(parents=True, exist_ok=True)
                archive.write_bytes(f"bundle-{job_id}".encode("ascii"))
                digest = campaign.sha256(archive)
                archive.with_name(archive.name + ".sha256").write_text(
                    f"{digest}  {archive.name}\n", encoding="ascii"
                )
                exported = root / "runs" / f"run_{job_id}"
                exported.mkdir()
                campaign.write_json(exported / "metadata.json", self.metadata(task, "9000", job_id))
                task_dir = root / "tasks" / f"task-{task['task_id']:03d}"
                campaign.write_json(task_dir / "bundle_verification.json", {
                    "verified": True, "complete": True, "validation": "passed",
                    "job_id": str(job_id), "files": 2193,
                })
                campaign.write_json(task_dir / "validation.json", {
                    "valid": True, "errors": [], "task_id": task["task_id"],
                    "job_id": str(job_id), "scientific_counts": {"islands": 144},
                })
                campaign.write_json(task_dir / "task.json", {
                    **task, "status": "completed", "exit_code": 0,
                    "array_job_id": "9000", "job_id": str(job_id),
                    "archive": str(archive.resolve()),
                })
            missing = root / "tasks/task-120/task.json"
            saved = missing.read_bytes()
            missing.unlink()
            with self.assertRaisesRegex(ValueError, "campaign validation failed"):
                campaign.finalize(root, "9000")
            self.assertFalse((root / "torus_best.tar.gz").exists())
            missing.write_bytes(saved)
            campaign.finalize(root, "9000")
            summary = campaign.read_json(root / "campaign_summary.json")
            self.assertTrue(summary["valid"])
            self.assertEqual(120, summary["valid_runs"])
            self.assertTrue((root / "torus_best.tar.gz.sha256").is_file())
            with tarfile.open(root / "torus_best.tar.gz", "r:gz") as stream:
                names = set(stream.getnames())
            self.assertIn("torus_best/campaign_summary.json", names)
            self.assertIn("torus_best/runs/r01_elliptic/repeat-1/run_100001.tar.gz", names)
            self.assertIn("torus_best/runs/b10_maxcut_ring/repeat-3/run_100120.tar.gz", names)

    def test_scientific_validation_reads_all_144_islands_and_rejects_damage(self):
        with tempfile.TemporaryDirectory(prefix="torus-best-science-") as temporary:
            root = Path(temporary)
            task = campaign.task_matrix()[0]
            plan_path = root / "campaign_plan.json"
            campaign.write_json(plan_path, campaign.expected_plan("a" * 40))
            raw = root / "storage/results/runs/sample"
            raw.mkdir(parents=True)
            metadata = self.metadata(task, "9000", "9001")
            campaign.write_json(raw / "run_metadata.json", metadata)
            campaign.write_json(raw / "experiment_manifest.json", {"status": "complete", "islands_completed": 144})
            campaign.write_json(raw / "benchmark_manifest.json", {"name": task["benchmark"], "dimension": 200})
            campaign.write_json(raw / "topology.json", {
                "name": "torus", "islands": 144,
                "torus_shape": {"rows": 12, "columns": 12},
                "graph_metrics": {"adjacency_sha256": "torus-hash"},
            })
            metadata["scientific_configuration"]["topology"]["adjacency_sha256"] = "torus-hash"
            campaign.write_json(raw / "run_metadata.json", metadata)
            campaign.write_json(raw / "metrics/data_contract.json", {"schema_version": 1})
            task_dir = root / "tasks/task-001"
            campaign.write_json(task_dir / "result_pointer.json", {
                "status": "complete", "run_id": "run-1", "run_directory": str(raw),
            })
            stream_payload = (b'{}\n' * 1997)
            for island in range(144):
                directory = raw / "metrics" / f"island_{island:03d}"
                directory.mkdir(parents=True)
                variables = [0] * 200
                digest = hashlib.sha256(json.dumps(variables, separators=(",", ":")).encode()).hexdigest()
                campaign.write_json(directory / "summary.json", {
                    "run_id": "run-1", "island": island,
                    "fitness_snapshot_records": 1997, "queue_fetch_records": 1997,
                    "sent_event_records": 1, "process_event_records": 1,
                    "local_duplicate_records": 0,
                    "final_solution_variables_sha256": digest,
                })
                campaign.write_json(directory / "runtime.json", {
                    "island": island, "actual_evaluations": 8000, "actual_steps": 1996,
                })
                campaign.write_json(directory / "final_solution.json", {
                    "run_id": "run-1", "island": island, "variables": variables,
                    "variable_count": 200, "variables_sha256": digest, "objectives": [1.0],
                })
                identity = {"run_id": "run-1", "recording_island": island, "event_id": f"{island}:1"}
                pair = (json.dumps({**identity, "record_type": "send"}) + "\n"
                        + json.dumps({**identity, "record_type": "process"}) + "\n")
                (directory / "migration_events.jsonl.gz").write_bytes(gzip.compress(pair.encode()))
                for name in ("queue_fetches.jsonl.gz", "fitness_history.jsonl.gz"):
                    (directory / name).write_bytes(gzip.compress(stream_payload))
            result = campaign.validate_run(root, plan_path, 1, "9000", "9001")
            self.assertTrue(result["valid"])
            self.assertEqual(144, result["scientific_counts"]["islands"])
            self.assertEqual(1.0, result["final_fitness"]["best"])
            (raw / "metrics/island_143/fitness_history.jsonl.gz").write_bytes(b"damaged")
            with self.assertRaises(ValueError):
                campaign.validate_run(root, plan_path, 1, "9000", "9001")
            self.assertFalse(campaign.read_json(task_dir / "validation.json")["valid"])


if __name__ == "__main__":
    unittest.main()
