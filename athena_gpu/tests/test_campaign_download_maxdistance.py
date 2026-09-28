"""Offline transfer checks for the ER4/maxDistance campaign tree."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from athena_gpu.tests.campaign_fixture import create_campaign


class MaxDistanceCampaignDownloaderTests(unittest.TestCase):
    def setUp(self):
        if os.name != "nt" or not shutil.which("powershell.exe"):
            self.skipTest("Windows PowerShell is required")
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.fixture = create_campaign(self.root, strategy="maxDistance")
        self.script = (Path(__file__).resolve().parents[1]
                       / "download_production_er4_maxdistance_120.ps1")

    def invoke(self, destination):
        command = (
            "Import-Module Microsoft.PowerShell.Utility; "
            "function scp { param([switch]$r, [string]$Source, [string]$Target) "
            "Write-Host 'MOCK_SCP_CALL=1'; "
            "Copy-Item -LiteralPath $env:FIXTURE_CAMPAIGN -Destination $Target -Recurse; "
            "$global:LASTEXITCODE=0 }; "
            f"& '{self.script}' -ArrayJobId 123 "
            f"-RemoteCampaignDir '/mock/er4_maxdistance_123' -Destination '{destination}'"
        )
        env = os.environ.copy()
        env["FIXTURE_CAMPAIGN"] = str(self.fixture["campaign"])
        return subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
            env=env, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=90,
        )

    def test_downloads_one_tree_checks_hashes_and_refuses_overwrite(self):
        destination = self.root / "download"
        result = self.invoke(destination)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(1, result.stdout.count("MOCK_SCP_CALL=1"))
        self.assertIn("ATHENA_ER4_MAXDISTANCE_DOWNLOADED_ARCHIVES_SHA256_OK=120/120",
                      result.stdout)
        self.assertTrue((destination / "er4_maxdistance_123/campaign_plan.json").is_file())
        self.assertEqual(120, len(list((destination / "er4_maxdistance_123/runs").rglob("run_*.tar.gz"))))
        again = self.invoke(destination)
        self.assertNotEqual(0, again.returncode)
        self.assertNotIn("MOCK_SCP_CALL=1", again.stdout)

    def test_bad_checksum_fails_without_claiming_success(self):
        bundle = self.fixture["campaign"] / "runs/r01_elliptic/repeat-1/run_501.tar.gz"
        bundle.write_bytes(b"corrupted")
        result = self.invoke(self.root / "bad")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("SHA-256 mismatch", result.stderr)
        self.assertNotIn("ATHENA_ER4_MAXDISTANCE_DOWNLOAD_OK", result.stdout)

    def test_missing_archive_or_checksum_fails_without_claiming_success(self):
        bundle = self.fixture["campaign"] / "runs/r01_elliptic/repeat-1/run_501.tar.gz"
        bundle.unlink()
        missing_archive = self.invoke(self.root / "missing-archive")
        self.assertNotEqual(0, missing_archive.returncode)
        self.assertIn("Incomplete download", missing_archive.stderr)
        self.assertNotIn("ATHENA_ER4_MAXDISTANCE_DOWNLOAD_OK", missing_archive.stdout)

        bundle.write_bytes(b"synthetic run 1\n")
        bundle.with_name(bundle.name + ".sha256").unlink()
        missing_checksum = self.invoke(self.root / "missing-checksum")
        self.assertNotEqual(0, missing_checksum.returncode)
        self.assertIn("Incomplete download", missing_checksum.stderr)
        self.assertNotIn("ATHENA_ER4_MAXDISTANCE_DOWNLOAD_OK", missing_checksum.stdout)


if __name__ == "__main__":
    unittest.main()
