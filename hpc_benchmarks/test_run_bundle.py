"""Portable artifact tests; no scheduler, Ray or GPU is started."""
import copy
import gzip
import io
import json
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_bundle as bundle


class BundleTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="run-bundle-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.raw = self.root / "raw with spaces"
        self.job = self.root / "job"
        self.logs = self.root / "slurm logs"
        for path in (self.raw, self.job, self.logs):
            path.mkdir()
        self.metadata = {
            "schema_version": 1, "status": "complete", "run_id": "scientific-123",
            "scientific_configuration": {
                "study": "approved-144", "islands": 2, "repeat": 3, "dimension": 200,
                "benchmark": {"name": "r01_elliptic", "suite": "benchmarks_refined"},
                "topology": {"name": "er4", "parameters": {"probab": 0.0347}},
                "migration": {"selection": "best", "acceptance": "plain", "interval": 5,
                              "interval_unit": "evaluation-count difference", "group_size": 5},
            },
            "resources": {"slurm": {"SLURM_JOB_ID": "123", "SLURM_ARRAY_JOB_ID": "120", "SLURM_ARRAY_TASK_ID": "3"}},
            "provenance": {"git_commit": "fixed-commit"},
            "outputs": {"run_directory": str(self.raw)},
        }
        for name in bundle.CORE_RESULTS:
            (self.raw / name).write_bytes(b"{\"preserved\":true}\n" if name.endswith(".json") else b"sample\x00binary\n")
        self.save_metadata()
        metrics = self.raw / "metrics"
        metrics.mkdir()
        bundle.write_json(metrics / "data_contract.json", {"schema_version": 1, "delay_definition": "source_step - process_step"})
        for i in range(2):
            directory = metrics / f"island_{i:03d}"
            directory.mkdir()
            for name in bundle.ISLAND_FILES:
                content = b'{"delay_steps":-5,"survival":null,"island":' + str(i).encode() + b'}\n'
                if name.endswith(".gz"):
                    content = gzip.compress(content)
                (directory / name).write_bytes(content)
        bundle.write_json(self.job / "result_pointer.json", {"run_directory": str(self.raw), "run_id": "scientific-123"})
        bundle.write_json(self.job / "validation.json", {"status": "passed", "valid": True})
        (self.job / "pip-freeze.txt").write_text("kept==1\n")
        (self.job / "cache").mkdir()
        (self.job / "cache/compiled.tmp").write_bytes(b"not research data")
        (self.logs / "pilot-120_3.out").write_text("finished\n")
        (self.logs / "pilot-120_3.err").touch()
        (self.logs / "benchmark-9123.out").write_text("another job\n")

    def save_metadata(self):
        bundle.write_json(self.raw / "run_metadata.json", self.metadata)

    def export(self, **kwargs):
        return bundle.export_run(**{
            "pointer": self.job / "result_pointer.json", "job_dir": self.job,
            "platform": "ares", "job_id": "123", "log_dir": self.logs,
            "output_root": self.root / "exports", **kwargs,
        })

    def test_complete_layout_preserves_all_original_payloads_and_relative_paths(self):
        before = {p.relative_to(self.raw): bundle.sha256(p) for p in bundle.files_under(self.raw)}
        result = self.export()
        target = Path(result["directory"])
        self.assertEqual({"logs", "metrics", "results", "identifier.txt", "metdadata.json"}, {p.name for p in target.iterdir()})
        self.assertFalse((target / "results/metrics").exists())
        self.assertFalse((target / "results/cache").exists())
        self.assertEqual({"pilot-120_3.out", "pilot-120_3.err"}, {p.name for p in (target / "logs").iterdir()})
        for relative, digest in before.items():
            exported = target / relative if relative.parts[0] == "metrics" else target / "results" / relative
            self.assertEqual(digest, bundle.sha256(exported), relative)
            self.assertEqual(digest, bundle.sha256(self.raw / relative), "source changed")
        self.assertEqual((self.raw / "run_metadata.json").read_bytes(), (target / bundle.METADATA).read_bytes())
        manifest = bundle.read_json(target / "results/bundle_manifest.json")
        self.assertEqual("metrics", manifest["paths"]["metrics"])
        self.assertEqual(bundle.result_directory(target), target / "results")
        self.assertEqual(bundle.metrics_directory(target / "results"), target / "metrics")
        self.assertTrue(bundle.verify_archive(result["archive"])["verified"])
        self.assertIn("repeat=3\n", (target / "identifier.txt").read_text())
        self.assertIn("validation=passed\n", (target / "identifier.txt").read_text())

    def test_cpu_gpu_common_contract_and_extra_gpu_metrics_are_preserved(self):
        cpu = self.export()
        extra = self.raw / "metrics/athena"
        extra.mkdir()
        (extra / "gpu_batches.jsonl.gz").write_bytes(gzip.compress(b'{"batch":144}\n'))
        self.metadata["execution_backend"] = "athena-gpu-sharded"
        self.save_metadata()
        gpu = self.export(platform="athena", output_root=self.root / "gpu-exports")
        for relative in ("metrics/data_contract.json", "metrics/island_000/migration_events.jsonl.gz",
                         "metrics/island_001/runtime.json", "results/param.json"):
            self.assertEqual((Path(cpu["directory"]) / relative).read_bytes(), (Path(gpu["directory"]) / relative).read_bytes())
        self.assertTrue((Path(gpu["directory"]) / "metrics/athena/gpu_batches.jsonl.gz").is_file())

    def test_missing_island_file_is_never_called_complete(self):
        (self.raw / "metrics/island_001/runtime.json").unlink()
        with self.assertRaisesRegex(ValueError, "incomplete scientific run"):
            self.export()
        result = self.export(allow_incomplete=True, exit_code=1)
        self.assertFalse(result["complete"])
        manifest = bundle.read_json(Path(result["directory"]) / "results/bundle_manifest.json")
        self.assertIn("metrics/island_001/runtime.json", manifest["missing"])

    def test_unvalidated_cpu_is_not_falsely_labelled_passed(self):
        (self.job / "validation.json").unlink()
        result = self.export()
        self.assertEqual("not_run", result["validation"])

    def test_failed_validation_is_preserved_even_with_complete_payload(self):
        bundle.write_json(self.job / "validation.json", {"valid": False, "status": "failed"})
        self.assertEqual("failed", self.export()["validation"])

    def test_identifier_preserves_canary_mode_from_validation_or_job_name(self):
        bundle.write_json(self.job / "validation.json", {"valid": True, "mode": "canary"})
        result = self.export()
        self.assertIn("mode=canary\n", (Path(result["directory"]) / "identifier.txt").read_text())
        (self.job / "validation.json").unlink()
        self.metadata["resources"]["slurm"]["SLURM_JOB_NAME"] = "island-pilot-canary"
        self.save_metadata()
        result = self.export(replace=True)
        self.assertIn("mode=canary\n", (Path(result["directory"]) / "identifier.txt").read_text())

    def test_wrong_job_or_pointer_identity_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "job ID mismatch"):
            self.export(job_id="124")
        bundle.write_json(self.job / "result_pointer.json", {"run_directory": str(self.raw), "run_id": "other"})
        with self.assertRaisesRegex(ValueError, "different runs"):
            self.export()

    def test_replacement_requires_explicit_flag_and_same_run(self):
        first = self.export()
        with self.assertRaises(FileExistsError):
            self.export()
        self.export(replace=True)
        self.metadata["run_id"] = "another-run"
        self.save_metadata()
        bundle.write_json(self.job / "result_pointer.json", {"run_directory": str(self.raw), "run_id": "another-run"})
        with self.assertRaisesRegex(ValueError, "another scientific run"):
            self.export(replace=True)
        self.assertTrue(bundle.verify_archive(first["archive"])["verified"])

    def test_conflicting_job_and_raw_files_do_not_overwrite_data(self):
        (self.job / "param.json").write_text('{"other":true}')
        with self.assertRaisesRegex(ValueError, "conflicting sources"):
            self.export()
        self.assertFalse((self.root / "exports/run_123.tar.gz").exists())

    def test_path_injection_and_recursive_export_are_rejected(self):
        for job in ("../123", "/123", "123/x", "123;cmd", ""):
            with self.subTest(job=job), self.assertRaises(ValueError):
                bundle.job_token(job)
        with self.assertRaisesRegex(ValueError, "outside source trees"):
            self.export(output_root=self.raw / "exports")

    def test_archive_corruption_is_detected(self):
        result = self.export()
        archive = Path(result["archive"])
        with archive.open("ab") as stream:
            stream.write(b"corruption")
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            bundle.verify_archive(archive)

    def test_early_failure_can_be_preserved_without_fabricating_metrics(self):
        result = bundle.export_run(output_root=self.root / "exports", platform="ares", job_id="123",
                                   log_dir=self.logs, allow_incomplete=True, exit_code=2)
        self.assertFalse(result["complete"])
        target = Path(result["directory"])
        self.assertEqual([], list((target / "metrics").iterdir()))
        self.assertEqual("failed", bundle.read_json(target / bundle.METADATA)["status"])

    def test_failure_preserves_audit_before_raw_directory_exists(self):
        audit = self.root / "audit"
        audit.mkdir()
        metadata = copy.deepcopy(self.metadata)
        metadata["status"] = "failed"
        bundle.write_json(audit / "run_metadata.json", metadata)
        bundle.write_json(audit / "experiment_manifest.json", {"error": "worker startup failed"})
        bundle.write_json(self.job / "result_pointer.json", {
            "run_id": metadata["run_id"], "run_directory": str(self.root / "not-created"),
            "run_metadata": str(audit / "run_metadata.json"), "audit_directory": str(audit),
        })
        result = self.export(allow_incomplete=True, exit_code=1)
        target = Path(result["directory"])
        self.assertEqual("worker startup failed", bundle.read_json(target / "results/experiment_manifest.json")["error"])
        self.assertEqual((audit / "run_metadata.json").read_bytes(), (target / "results/run_metadata.json").read_bytes())
        self.assertFalse(result["complete"])


if __name__ == "__main__":
    unittest.main()
