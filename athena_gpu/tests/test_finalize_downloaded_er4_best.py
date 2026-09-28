"""Offline final aggregate from real-format but tiny portable run bundles."""
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

from athena_gpu.finalize_downloaded_er4_best import audit_downloaded, finalize_downloaded
from athena_gpu.tests.campaign_fixture import create_campaign


def add_bytes(stream, name, payload):
    member = tarfile.TarInfo(name)
    member.size = len(payload)
    stream.addfile(member, io.BytesIO(payload))


def create_portable_bundles(fixture):
    campaign, plan = fixture["campaign"], fixture["plan"]
    strategy = plan["configuration"]["migration"]["selection"]
    for task in plan["tasks"]:
        task_id = task["task_id"]
        job_id = str(500 + task_id)
        record_path = campaign / "tasks" / f"task-{task_id:03d}.json"
        record = json.loads(record_path.read_text(encoding="utf-8"))
        bundle = campaign / record["archive"]
        config = plan["configuration"]
        metadata = {
            "status": "complete", "run_id": f"run-id-{task_id}",
            "experiment_key": hashlib.sha256(task["benchmark"].encode()).hexdigest(),
            "provenance": {"git_commit": "b" * 40, "runtime_sha256": "c" * 64},
            "resources": {"slurm": {
                "SLURM_JOB_ID": job_id, "SLURM_ARRAY_JOB_ID": "123",
                "SLURM_ARRAY_TASK_ID": str(task_id),
            }},
            "scientific_configuration": {
                "benchmark": {"name": task["benchmark"], "implementation_sha256": "d" * 64},
                "dimension": 200, "islands": 144, "evaluations_per_island": 8000,
                "population": 16, "offspring": 4, "repeat": task["repeat"],
                "migration": config["migration"], "topology": config["topology"],
                "metrics": {"profile": config["metrics_profile"]},
                "seed": {"requested_base": 20260912,
                         "repeat_base": task["repeat_seed"],
                         "benchmark_instance_seed": 20260511},
            },
        }
        validation = {
            "status": "passed", "valid": True, "errors": [], "mode": "full",
            "benchmark": task["benchmark"], "dimension": 200, "topology": "er4",
            "migrant_selection": strategy, "migrant_acceptance": "plain",
            "repeat": task["repeat"], "base_seed": 20260912,
            "repeat_seed": task["repeat_seed"], "git_commit": "b" * 40,
        }
        root = f"run_{job_id}"
        metadata_bytes = json.dumps(metadata).encode()
        payloads = {
            "identifier.txt": f"job_id={job_id}\n".encode(),
            "metadata.json": metadata_bytes,
            "metrics/data_contract.json": b"{}\n",
            "results/run_metadata.json": metadata_bytes,
            "results/validation.json": json.dumps(validation).encode(),
            f"logs/athena-er4-{strategy.lower()}-120-123_{task_id}.out": b"available snapshot\n",
        }
        manifest = {
            "schema": "islandsea-run-bundle-v1", "job_id": job_id,
            "platform": "athena", "complete": True, "validation": "passed",
            "scientific_status": "complete", "job_exit_code": 0,
            "files": {name: {"bytes": len(data),
                              "sha256": hashlib.sha256(data).hexdigest()}
                      for name, data in payloads.items()},
        }
        with tarfile.open(bundle, "w:gz") as stream:
            for directory in (root, f"{root}/logs", f"{root}/metrics", f"{root}/results"):
                member = tarfile.TarInfo(directory)
                member.type = tarfile.DIRTYPE
                stream.addfile(member)
            for name, data in payloads.items():
                add_bytes(stream, f"{root}/{name}", data)
            add_bytes(stream, f"{root}/results/bundle_manifest.json",
                      json.dumps(manifest).encode())
        digest = hashlib.sha256(bundle.read_bytes()).hexdigest()
        bundle.with_name(bundle.name + ".sha256").write_text(
            f"{digest}  {bundle.name}\n", encoding="ascii"
        )
        record["archive_sha256"] = digest
        record_path.write_text(json.dumps(record), encoding="utf-8")


class LocalFinalizerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.fixture = create_campaign(Path(self.temporary.name))
        create_portable_bundles(self.fixture)
        self.campaign = self.fixture["campaign"]

    def test_audit_and_ares_style_archive_preserve_run_bytes(self):
        summary, entries, captured = audit_downloaded(self.campaign, "123")
        self.assertEqual(120, summary["valid_runs"])
        self.assertFalse(summary["independent_sacct_in_archive"])
        self.assertEqual(120, len(entries))
        self.assertIn("validations/task-001.json", captured)
        source = self.campaign / entries[0]["archive"]
        original = source.read_bytes()
        result = finalize_downloaded(self.campaign, "123", self.campaign.parent)
        archive = Path(result["archive"])
        self.assertEqual("er4_best.tar.gz", archive.name)
        self.assertEqual(original, source.read_bytes())
        with tarfile.open(archive, "r:gz") as stream:
            names = stream.getnames()
            self.assertTrue(all(name.startswith("er4_best/") for name in names))
            self.assertIn("er4_best/campaign_plan.json", names)
            self.assertIn("er4_best/campaign_summary.json", names)
            self.assertIn("er4_best/task_records/task-001.json", names)
            self.assertIn("er4_best/validations/task-001.json", names)
            self.assertIn("er4_best/logs/athena-er4-best-120-123_1.out", names)
            self.assertEqual(120, sum(name.endswith(".tar.gz") for name in names))
            self.assertEqual(original, stream.extractfile("er4_best/" + entries[0]["archive"]).read())
        with self.assertRaises(FileExistsError):
            finalize_downloaded(self.campaign, "123", self.campaign.parent)

    def test_missing_checksum_blocks_aggregate(self):
        first = self.campaign / "runs/r01_elliptic/repeat-1/run_501.tar.gz"
        sidecar = first.with_name(first.name + ".sha256")
        sidecar.unlink()
        with self.assertRaisesRegex(ValueError, "checksum"):
            audit_downloaded(self.campaign, "123")
        self.assertFalse((self.campaign.parent / "er4_best.tar.gz").exists())

    def test_missing_or_corrupted_archive_blocks_aggregate(self):
        first = self.campaign / "runs/r01_elliptic/repeat-1/run_501.tar.gz"
        original = first.read_bytes()
        first.unlink()
        with self.assertRaisesRegex(ValueError, "archive"):
            audit_downloaded(self.campaign, "123")
        first.write_bytes(original + b"corrupted")
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            audit_downloaded(self.campaign, "123")
        self.assertFalse((self.campaign.parent / "er4_best.tar.gz").exists())

    def test_random_campaign_uses_same_portable_formula_without_best_leak(self):
        other = Path(self.temporary.name) / "random"
        fixture = create_campaign(other, strategy="random")
        create_portable_bundles(fixture)
        summary, entries, captured = audit_downloaded(fixture["campaign"], "123", "random")
        self.assertEqual("er4_random", summary["campaign"])
        self.assertEqual(120, summary["valid_runs"])
        self.assertEqual(120, len(entries))
        self.assertIn("logs/athena-er4-random-120-123_1.out", captured)
        with self.assertRaises(ValueError):
            audit_downloaded(fixture["campaign"], "123", "best")
        result = finalize_downloaded(fixture["campaign"], "123", other, "random")
        self.assertEqual("er4_random.tar.gz", Path(result["archive"]).name)
        with tarfile.open(result["archive"], "r:gz") as stream:
            names = stream.getnames()
            self.assertTrue(all(name.startswith("er4_random/") for name in names))
            self.assertEqual(120, sum(name.endswith(".tar.gz") for name in names))
            plan = json.load(stream.extractfile("er4_random/campaign_plan.json"))
            self.assertEqual("random", plan["configuration"]["migration"]["selection"])

    def test_maxdistance_campaign_uses_ares_style_lowercase_archive_name(self):
        other = Path(self.temporary.name) / "maxdistance"
        fixture = create_campaign(other, strategy="maxDistance")
        create_portable_bundles(fixture)
        summary, entries, captured = audit_downloaded(fixture["campaign"], "123", "maxDistance")
        self.assertEqual("er4_maxdistance", summary["campaign"])
        self.assertEqual(120, summary["valid_runs"])
        self.assertEqual(120, len(entries))
        self.assertIn("logs/athena-er4-maxdistance-120-123_1.out", captured)
        with self.assertRaises(ValueError):
            audit_downloaded(fixture["campaign"], "123", "random")
        result = finalize_downloaded(fixture["campaign"], "123", other, "maxDistance")
        self.assertEqual("er4_maxdistance.tar.gz", Path(result["archive"]).name)
        with tarfile.open(result["archive"], "r:gz") as stream:
            names = stream.getnames()
            self.assertTrue(all(name.startswith("er4_maxdistance/") for name in names))
            self.assertEqual(120, sum(name.endswith(".tar.gz") for name in names))
            plan = json.load(stream.extractfile("er4_maxdistance/campaign_plan.json"))
            self.assertEqual("maxDistance", plan["configuration"]["migration"]["selection"])


if __name__ == "__main__":
    unittest.main()
