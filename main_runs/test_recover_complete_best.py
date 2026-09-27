"""The recovery must reuse validated scientific output and preserve failure provenance."""

from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import recover_complete_best as recovery


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "complete_best"
        self.task_dir = self.root / "tasks/task-001"
        self.task_dir.mkdir(parents=True)
        self.raw = self.root / "storage/results/runs/one"
        self.raw.mkdir(parents=True)
        self.plan = {"git_commit_at_submission": "a" * 40}
        self.task = {"task_id": 1, "benchmark": "r01_elliptic", "repeat": 1}
        self.record = {**self.task, "array_job_id": "9000", "execution_array_job_id": "9000",
                       "job_id": "9001", "status": "failed", "exit_code": 74,
                       "finished_utc": "original-failure"}
        recovery.campaign.write_json(self.task_dir / "task.json", self.record)
        recovery.campaign.write_json(self.task_dir / "validation.json", {
            "valid": True, "errors": [], "task_id": 1, "job_id": "9001",
            "array_job_id": "9000", "execution_array_job_id": "9000",
        })
        recovery.campaign.write_json(self.task_dir / "result_pointer.json", {
            "run_directory": str(self.raw), "run_id": "scientific-one",
        })
        recovery.campaign.write_json(self.raw / "run_metadata.json", {
            "run_id": "scientific-one", "provenance": {"git_commit": "a" * 40},
        })

    def inspect(self):
        with mock.patch.object(recovery.campaign, "task_for", return_value=self.task), \
             mock.patch.object(recovery.campaign, "validate_metadata", return_value=[]):
            return recovery.inspect_task(self.root, self.plan, 1, "9000")

    def test_preflight_accepts_only_validated_original_packaging_failure(self):
        self.assertEqual("9001", self.inspect()[3])
        invalid = recovery.campaign.read_json(self.task_dir / "validation.json")
        invalid["valid"] = False
        recovery.campaign.write_json(self.task_dir / "validation.json", invalid)
        with self.assertRaisesRegex(ValueError, "scientific validation"):
            self.inspect()

    def test_recovery_records_original_exit_and_recovery_job_separately(self):
        archive = self.root / "runs/run_9001.tar.gz"
        with mock.patch.object(recovery, "load_campaign", return_value=(self.root, self.plan, "9000")), \
             mock.patch.object(recovery, "inspect_task", return_value=(
                 self.task_dir, self.record, self.task_dir / "result_pointer.json", "9001")), \
             mock.patch.object(recovery.run_bundle, "export_run", return_value={"archive": str(archive)}) as export, \
             mock.patch.object(recovery.run_bundle, "verify_archive", return_value={
                 "verified": True, "complete": True, "validation": "passed", "job_id": "9001",
             }):
            recovery.recover_task(self.root, 1, "9101")
        self.assertEqual(74, export.call_args.kwargs["exit_code"])
        record = recovery.campaign.read_json(self.task_dir / "task.json")
        self.assertEqual("completed", record["status"])
        self.assertEqual(0, record["exit_code"])
        self.assertEqual(74, record["original_job_exit_code"])
        self.assertEqual("9101", record["recovery_job_id"])
        self.assertEqual("9001", record["job_id"])


if __name__ == "__main__":
    unittest.main()
