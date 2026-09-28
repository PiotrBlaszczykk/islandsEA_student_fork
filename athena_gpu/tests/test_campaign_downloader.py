"""Offline PowerShell checks of one-connection aggregate campaign downloads."""
import hashlib
import io
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from athena_gpu.campaign_er4_best import finalize_campaign
from athena_gpu.tests.campaign_fixture import create_campaign
from athena_gpu.tests.test_campaign_finalizer import fake_verify


class CampaignDownloaderTests(unittest.TestCase):
    def setUp(self):
        if os.name != "nt" or not shutil.which("powershell.exe"):
            self.skipTest("Windows PowerShell is required")
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        fixture = create_campaign(self.root)
        with patch("athena_gpu.campaign_er4_best.verify_archive", side_effect=fake_verify):
            result = finalize_campaign(fixture["campaign"], "123", fixture["results"],
                                       fixture["logs"], fixture["sacct"])
        self.archive = Path(result["archive"])
        self.checksum = Path(result["checksum"])
        self.script = Path(__file__).resolve().parents[1] / "download_production_er4_best_120.ps1"

    def invoke(self, destination: Path, *, extract=False, copy_archive=True, copy_checksum=True):
        options = "-Extract" if extract else ""
        command = (
            "Import-Module Microsoft.PowerShell.Utility; "
            "function scp { param([string]$Source, [string]$Target) "
            "Write-Host 'MOCK_SCP_CALL=1'; "
            "if ($env:COPY_ARCHIVE -eq '1') { Copy-Item -LiteralPath $env:FIXTURE_ARCHIVE -Destination $Target }; "
            "if ($env:COPY_CHECKSUM -eq '1') { Copy-Item -LiteralPath $env:FIXTURE_CHECKSUM -Destination $Target }; "
            "$global:LASTEXITCODE=0 }; "
            f"& '{self.script}' -ArrayJobId 123 -RemoteCampaignDir '/mock/er4_best_123' "
            f"-Destination '{destination}' {options}"
        )
        env = os.environ.copy()
        env.update(FIXTURE_ARCHIVE=str(self.archive), FIXTURE_CHECKSUM=str(self.checksum),
                   COPY_ARCHIVE="1" if copy_archive else "0",
                   COPY_CHECKSUM="1" if copy_checksum else "0")
        return subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
            env=env, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=90,
        )

    def test_default_downloads_only_two_files_in_one_scp_call(self):
        destination = self.root / "download"
        result = self.invoke(destination)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(1, result.stdout.count("MOCK_SCP_CALL=1"))
        self.assertIn("ATHENA_ER4_BEST_SHA256_OK=", result.stdout)
        self.assertTrue((destination / self.archive.name).is_file())
        self.assertTrue((destination / self.checksum.name).is_file())
        self.assertFalse((destination / "er4_best_123").exists())
        again = self.invoke(destination)
        self.assertNotEqual(0, again.returncode)
        self.assertNotIn("MOCK_SCP_CALL=1", again.stdout)

    def test_extract_checks_120_nested_hashes_and_layout(self):
        destination = self.root / "extracted"
        result = self.invoke(destination, extract=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("ATHENA_ER4_BEST_NESTED_SHA256_OK=120", result.stdout)
        campaign = destination / "er4_best_123"
        self.assertTrue((campaign / "campaign_plan.json").is_file())
        self.assertTrue((campaign / "campaign_summary.json").is_file())
        self.assertTrue((campaign / "tasks/task-120.json").is_file())
        self.assertTrue((campaign / "validations/task-120.json").is_file())
        self.assertTrue((campaign / "logs/athena-er4-best-120-123_1.out").is_file())
        self.assertEqual(120, len(list((campaign / "runs").rglob("run_*.tar.gz"))))

    def test_missing_archive_checksum_and_corruption_fail_closed(self):
        for label, archive, checksum in (
            ("no_archive", False, True), ("no_checksum", True, False)
        ):
            with self.subTest(label=label):
                result = self.invoke(self.root / label, copy_archive=archive,
                                     copy_checksum=checksum)
                self.assertNotEqual(0, result.returncode)
                self.assertIn("archive or checksum is missing", result.stderr)
        original = self.archive.read_bytes()
        self.archive.write_bytes(b"corrupted aggregate")
        result = self.invoke(self.root / "corrupt")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("SHA-256 mismatch", result.stderr)
        self.archive.write_bytes(original)

    def test_extract_rejects_bad_nested_archive_even_when_outer_hash_matches(self):
        altered = self.root / "altered.tar.gz"
        with tarfile.open(self.archive, "r:gz") as source, tarfile.open(altered, "w:gz") as target:
            for member in source:
                content = source.extractfile(member).read()
                if member.name.endswith("/run_501.tar.gz"):
                    content = b"changed nested bundle"
                replacement = tarfile.TarInfo(member.name)
                replacement.size = len(content)
                target.addfile(replacement, io.BytesIO(content))
        self.archive.write_bytes(altered.read_bytes())
        digest = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        self.checksum.write_text(f"{digest}  {self.archive.name}\n", encoding="ascii")
        result = self.invoke(self.root / "bad_nested", extract=True)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("Nested archive SHA-256 mismatch", result.stderr)

    def test_existing_extracted_directory_is_never_overwritten(self):
        destination = self.root / "existing"
        (destination / "er4_best_123").mkdir(parents=True)
        sentinel = destination / "er4_best_123" / "user-file.txt"
        sentinel.write_text("preserve", encoding="utf-8")
        result = self.invoke(destination, extract=True)
        self.assertNotEqual(0, result.returncode)
        self.assertIn("Destination already exists", result.stderr)
        self.assertNotIn("MOCK_SCP_CALL=1", result.stdout)
        self.assertEqual("preserve", sentinel.read_text(encoding="utf-8"))
        archive_only = self.invoke(destination)
        self.assertEqual(0, archive_only.returncode, archive_only.stderr)
        self.assertEqual("preserve", sentinel.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
