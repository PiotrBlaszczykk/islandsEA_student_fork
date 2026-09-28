"""No-GPU checks of fail-closed campaign audit and aggregate layout."""
import hashlib
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from athena_gpu.campaign_er4_best import finalize_campaign
from athena_gpu.tests.campaign_fixture import create_campaign


def fake_verify(path):
    return {"verified": True, "job_id": path.name[4:-7],
            "complete": True, "validation": "passed"}


class CampaignFinalizerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.fixture = create_campaign(Path(self.temporary.name))
        self.campaign = self.fixture["campaign"]

    def finalize(self):
        with patch("athena_gpu.campaign_er4_best.verify_archive", side_effect=fake_verify):
            return finalize_campaign(
                self.campaign, "123", self.fixture["results"],
                self.fixture["logs"], self.fixture["sacct"]
            )

    def test_success_has_one_root_120_unmodified_bundles_and_only_real_logs(self):
        (self.campaign / "logs").mkdir()
        (self.campaign / "logs/finalize-999.out").write_text("snapshot\n", encoding="utf-8")
        result = self.finalize()
        self.assertEqual(120, result["valid_runs"])
        archive = Path(result["archive"])
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        self.assertEqual(f"{digest}  {archive.name}", Path(result["checksum"]).read_text().strip())
        summary = json.loads(Path(result["summary"]).read_text(encoding="utf-8"))
        self.assertEqual(120, summary["valid_runs"])
        self.assertEqual(["athena-er4-best-120-123_1.out"], summary["available_logs"])
        self.assertEqual(["finalize-999.out"], summary["finalizer_log_snapshots"])
        self.assertIn("athena-er4-best-120-123_2.out", summary["missing_logs"])
        with tarfile.open(archive, "r:gz") as stream:
            names = stream.getnames()
            self.assertTrue(all(name.startswith("er4_best_123/") for name in names))
            self.assertIn("er4_best_123/campaign_plan.json", names)
            self.assertIn("er4_best_123/campaign_summary.json", names)
            self.assertIn("er4_best_123/tasks/task-120.json", names)
            self.assertIn("er4_best_123/validations/task-120.json", names)
            self.assertIn("er4_best_123/logs/athena-er4-best-120-123_1.out", names)
            self.assertIn("er4_best_123/logs/finalize-999.out", names)
            self.assertNotIn("er4_best_123/logs/athena-er4-best-120-123_2.out", names)
            nested = [name for name in names if name.endswith(".tar.gz")]
            checksums = [name for name in names if name.endswith(".tar.gz.sha256")]
            self.assertEqual(120, len(nested))
            self.assertEqual(120, len(checksums))
            first = summary["runs"][0]
            self.assertEqual(
                (self.campaign / first["archive"]).read_bytes(),
                stream.extractfile("er4_best_123/" + first["archive"]).read(),
            )
        with self.assertRaises(FileExistsError):
            self.finalize()

    def test_missing_or_corrupt_bundle_and_checksum_fail_without_aggregate(self):
        bundle = self.campaign / "runs/r01_elliptic/repeat-1/run_501.tar.gz"
        for mutation in ("missing_bundle", "missing_checksum", "corrupt_bundle", "bad_checksum"):
            with self.subTest(mutation=mutation):
                original = bundle.read_bytes()
                checksum = bundle.with_name(bundle.name + ".sha256")
                original_checksum = checksum.read_bytes()
                if mutation == "missing_bundle":
                    bundle.unlink()
                elif mutation == "missing_checksum":
                    checksum.unlink()
                elif mutation == "corrupt_bundle":
                    bundle.write_bytes(b"changed")
                else:
                    checksum.write_text("bad checksum\n", encoding="ascii")
                with self.assertRaises((ValueError, FileNotFoundError)):
                    self.finalize()
                self.assertFalse((self.campaign / "er4_best_123.tar.gz").exists())
                bundle.write_bytes(original)
                checksum.write_bytes(original_checksum)

    def test_missing_validation_or_failed_slurm_state_is_not_certified(self):
        validation = self.fixture["results"] / "501" / "validation.json"
        original = validation.read_bytes()
        validation.unlink()
        with self.assertRaisesRegex(ValueError, "validation"):
            self.finalize()
        validation.write_bytes(original)
        sacct = self.fixture["sacct"]
        sacct.write_text(sacct.read_text().replace("501|123_1|COMPLETED|0:0",
                                                   "501|123_1|FAILED|1:0"), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "did not complete"):
            self.finalize()
        self.assertFalse((self.campaign / "er4_best_123.tar.gz").exists())

    def test_missing_record_or_extra_bundle_is_not_silently_ignored(self):
        record = self.campaign / "tasks/task-120.json"
        original = record.read_bytes()
        record.unlink()
        with self.assertRaisesRegex(ValueError, "120 planned task records"):
            self.finalize()
        record.write_bytes(original)
        extra = self.campaign / "runs/r01_elliptic/repeat-1/run_999.tar.gz"
        extra.write_bytes(b"not planned")
        with self.assertRaisesRegex(ValueError, "unexpected bundle files"):
            self.finalize()
        self.assertFalse((self.campaign / "er4_best_123.tar.gz").exists())

    def test_random_finalizer_keeps_its_own_namespace_and_strategy(self):
        fixture = create_campaign(Path(self.temporary.name) / "random", strategy="random")
        with patch("athena_gpu.campaign_er4_best.verify_archive", side_effect=fake_verify):
            result = finalize_campaign(fixture["campaign"], "123", fixture["results"],
                                       fixture["logs"], fixture["sacct"], "random")
        archive = Path(result["archive"])
        self.assertEqual("er4_random_123.tar.gz", archive.name)
        summary = json.loads(Path(result["summary"]).read_text(encoding="utf-8"))
        self.assertEqual("er4_random", summary["campaign"])
        self.assertEqual(["athena-er4-random-120-123_1.out"], summary["available_logs"])
        with tarfile.open(archive, "r:gz") as stream:
            self.assertTrue(all(name.startswith("er4_random_123/") for name in stream.getnames()))
            self.assertEqual(120, sum(name.endswith(".tar.gz") for name in stream.getnames()))

    def test_maxdistance_finalizer_keeps_lowercase_paths_and_exact_strategy(self):
        fixture = create_campaign(Path(self.temporary.name) / "maxdistance", strategy="maxDistance")
        with patch("athena_gpu.campaign_er4_best.verify_archive", side_effect=fake_verify):
            result = finalize_campaign(fixture["campaign"], "123", fixture["results"],
                                       fixture["logs"], fixture["sacct"], "maxDistance")
        archive = Path(result["archive"])
        self.assertEqual("er4_maxdistance_123.tar.gz", archive.name)
        summary = json.loads(Path(result["summary"]).read_text(encoding="utf-8"))
        self.assertEqual("er4_maxdistance", summary["campaign"])
        self.assertEqual(["athena-er4-maxdistance-120-123_1.out"], summary["available_logs"])
        with tarfile.open(archive, "r:gz") as stream:
            self.assertTrue(all(name.startswith("er4_maxdistance_123/") for name in stream.getnames()))
            self.assertEqual(120, sum(name.endswith(".tar.gz") for name in stream.getnames()))
            validation = json.load(stream.extractfile("er4_maxdistance_123/validations/task-001.json"))
            self.assertEqual("maxDistance", validation["migrant_selection"])


if __name__ == "__main__":
    unittest.main()
