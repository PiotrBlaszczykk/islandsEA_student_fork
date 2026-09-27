"""Offline Windows check of the one-command 120-run campaign downloader."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from athena_gpu.campaign_er4_best import plan_document


class CampaignDownloaderTests(unittest.TestCase):
    def test_download_checks_all_120_task_records_and_archives(self):
        if os.name != "nt" or not shutil.which("powershell.exe"):
            self.skipTest("Windows PowerShell is required")
        script = Path(__file__).resolve().parents[1] / "download_production_er4_best_120.ps1"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source" / "er4_best_123"
            source.mkdir(parents=True)
            plan = plan_document("123", "a" * 40)
            (source / "campaign_plan.json").write_text(json.dumps(plan), encoding="utf-8")
            for task in plan["tasks"]:
                task_id = task["task_id"]
                job_id = str(500 + task_id)
                relative = Path("runs") / task["benchmark"] / f"repeat-{task['repeat']}"
                directory = source / relative
                directory.mkdir(parents=True, exist_ok=True)
                archive = directory / f"run_{job_id}.tar.gz"
                archive.write_bytes(f"synthetic {task_id}".encode("ascii"))
                digest = hashlib.sha256(archive.read_bytes()).hexdigest()
                (directory / (archive.name + ".sha256")).write_text(
                    f"{digest}  {archive.name}\n", encoding="ascii"
                )
                records = source / "tasks"
                records.mkdir(exist_ok=True)
                (records / f"task-{task_id:03d}.json").write_text(json.dumps({
                    "schema": plan["schema"], "status": "completed",
                    "array_job_id": "123", "task_id": task_id,
                    "job_id": job_id, "benchmark": task["benchmark"],
                    "dimension": 200, "repeat": task["repeat"],
                    "topology": "er4", "migrant_selection": "best",
                    "migrant_acceptance": "plain", "bundle_complete": True,
                    "validation": "passed",
                    "git_commit": "b" * 40,
                    "archive": (relative / archive.name).as_posix(),
                    "archive_sha256": digest,
                }), encoding="utf-8")
            destination = root / "download"
            command = (
                "Import-Module Microsoft.PowerShell.Utility; "
                "function scp { param([switch]$r, [string]$source, [string]$destination) "
                "Copy-Item -LiteralPath $env:CAMPAIGN_FIXTURE -Destination $destination -Recurse; "
                "$global:LASTEXITCODE=0 }; "
                f"& '{script}' -ArrayJobId 123 -RemoteCampaignDir '/mock/er4_best_123' "
                f"-Destination '{destination}'"
            )
            environment = os.environ.copy()
            environment["CAMPAIGN_FIXTURE"] = str(source)
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
                env=environment,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=45,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("ATHENA_ER4_BEST_VALID_RUNS=120", result.stdout)
            self.assertTrue((destination / "er4_best_123" / "campaign_plan.json").is_file())
            summary = json.loads(
                (destination / "er4_best_123" / "campaign_summary.json").read_text(encoding="utf-8")
            )
            self.assertTrue(summary["valid"])
            self.assertEqual(120, summary["valid_runs"])
            archive.write_bytes(b"corrupted after checksum")
            corrupted_destination = root / "corrupted_download"
            corrupted = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                 command.replace(str(destination), str(corrupted_destination))],
                env=environment,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=45,
            )
            self.assertNotEqual(0, corrupted.returncode)
            self.assertIn("SHA-256 mismatch", corrupted.stderr)


if __name__ == "__main__":
    unittest.main()
