"""Exercise submission guards with fake git/sbatch; no cluster is contacted."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


def bash_path(path):
    value = Path(path).resolve().as_posix()
    return "/" + value[0].lower() + value[2:] if os.name == "nt" else value


class SubmitterTests(unittest.TestCase):
    def setUp(self):
        self.bash = "C:/Program Files/Git/bin/bash.exe" if os.name == "nt" else shutil.which("bash")
        if not self.bash or not Path(self.bash).is_file():
            self.skipTest("Bash is required for launcher guard tests")
        self.scripts = Path(__file__).resolve().parents[1]
        temporary_root = self.scripts.parent / "tmp" / "athena_submitter_tests"
        temporary_root.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="case-", dir=temporary_root)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        self.write_executable(bin_dir / "git", '''#!/usr/bin/env bash
case "$*" in
    "branch --show-current") echo summer_benchmarks_athena ;;
    "status --porcelain --untracked-files=all")
        if [[ "${MOCK_DIRTY:-0}" == 1 ]]; then echo ' M changed.py'; fi ;;
    "status --short") echo ' M changed.py' ;;
    "rev-parse HEAD"|"rev-parse @{upstream}") echo abcdef123 ;;
    *) exit 99 ;;
esac
''')
        self.write_executable(bin_dir / "sbatch", '''#!/usr/bin/env bash
printf '%s\\n' "$@" > "$MOCK_CAPTURE"
echo 987654
''')
        venv_bin = self.root / "venv" / "bin"
        venv_bin.mkdir(parents=True)
        self.write_executable(venv_bin / "python", "#!/usr/bin/env bash\nexit 99\n")
        self.capture = self.root / "submission.txt"
        self.env = os.environ.copy()
        for key in ("SLURM_JOB_ID", "ISLANDS_STORAGE_ROOT", "ISLANDS_SLURM_LOG_DIR", "ATHENA_READINESS_ROOT", "ATHENA_BENCHMARK_VALIDATION_ROOT"):
            self.env.pop(key, None)
        self.env.update(MOCK_BIN=bash_path(bin_dir), MOCK_CAPTURE=bash_path(self.capture),
                        ISLANDS_VENV_DIR=bash_path(venv_bin.parent), SCRATCH=bash_path(self.root / "scratch"))

    @staticmethod
    def write_executable(path, text):
        path.write_bytes(text.encode("utf-8"))
        path.chmod(0o755)

    def submit(self, script):
        self.env["SUBMITTER"] = bash_path(self.scripts / script)
        return subprocess.run([self.bash, "-c", 'export PATH="$MOCK_BIN:$PATH"; exec bash "$SUBMITTER"'],
                              env=self.env, text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=30)

    def test_suite_uses_one_bounded_gpu_job_and_its_own_results(self):
        result = self.submit("submit_validation.sh")
        self.assertEqual(0, result.returncode, result.stderr)
        arguments = self.capture.read_text().splitlines()
        for flag in ("--nodes=1", "--cpus-per-task=16", "--mem=128000M", "--gres=gpu:1", "--time=00:15:00",
                     "--account=plgintobl-gpu-a100", "--partition=plgrid-gpu-a100"):
            self.assertIn(flag, arguments)
        self.assertIn("ATHENA_VALIDATION_MODE=suite", "\n".join(arguments))
        self.assertIn("results/athena_benchmark_validation/987654/validation.json", result.stdout)
        self.assertIn("MAX_GPU_HOURS=0.25", result.stdout)

    def test_original_f1_entrypoint_is_preserved(self):
        result = self.submit("submit_readiness.sh")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("ATHENA_VALIDATION_MODE=f1", self.capture.read_text())
        self.assertIn("results/athena_gpu_readiness/987654/readiness.json", result.stdout)

    def test_dirty_checkout_allocation_and_scratch_escape_never_submit(self):
        cases = ({"MOCK_DIRTY": "1"}, {"SLURM_JOB_ID": "42"},
                 {"ATHENA_BENCHMARK_VALIDATION_ROOT": bash_path(self.root / "outside-scratch")},
                 {"ISLANDS_SLURM_LOG_DIR": self.env["SCRATCH"] + "/../escaped-logs"})
        initial = self.env.copy()
        for changes in cases:
            with self.subTest(changes=changes):
                self.env = dict(initial, **changes)
                result = self.submit("submit_validation.sh")
                self.assertNotEqual(0, result.returncode)
                self.assertFalse(self.capture.exists(), result.stdout)


if __name__ == "__main__":
    unittest.main()
