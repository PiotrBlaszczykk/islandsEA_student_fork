"""Submission guard tests with fake git/sbatch; no cluster is contacted."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


def bash_path(path):
    value = Path(path).resolve().as_posix()
    return "/" + value[0].lower() + value[2:] if os.name == "nt" else value


class StudySubmitterTests(unittest.TestCase):
    def setUp(self):
        self.bash = "C:/Program Files/Git/bin/bash.exe" if os.name == "nt" else shutil.which("bash")
        if not self.bash or not Path(self.bash).is_file():
            self.skipTest("Bash is required")
        self.scripts = Path(__file__).resolve().parents[1]
        temp_root = self.scripts.parent / "tmp" / "athena_study_submitter_tests"
        temp_root.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="case-", dir=temp_root)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        self.write_executable(
            bin_dir / "git",
            '''#!/usr/bin/env bash
case "$*" in
    "branch --show-current") echo summer_benchmarks_athena ;;
    "status --porcelain --untracked-files=all")
        if [[ "${MOCK_DIRTY:-0}" == 1 ]]; then echo ' M changed.py'; fi ;;
    "status --short") echo ' M changed.py' ;;
    "rev-parse HEAD"|"rev-parse @{upstream}") echo abcdef123 ;;
    *) exit 99 ;;
esac
''',
        )
        self.write_executable(
            bin_dir / "sbatch",
            '''#!/usr/bin/env bash
printf '%s\n' "$@" > "$MOCK_CAPTURE"
echo 7654321
''',
        )
        # The Codex Windows sandbox grants native Python access to the
        # workspace but MSYS mkdir runs under a different ACL view. Directory
        # creation is not the behaviour under test; path guards and the exact
        # captured sbatch arguments are.
        self.write_executable(bin_dir / "mkdir", "#!/usr/bin/env bash\nexit 0\n")
        self.write_executable(bin_dir / "module", "#!/usr/bin/env bash\nexit 0\n")
        venv_bin = self.root / "venv" / "bin"
        venv_bin.mkdir(parents=True)
        self.write_executable(venv_bin / "python", "#!/usr/bin/env bash\nexit 0\n")
        self.capture = self.root / "submission.txt"
        self.env = os.environ.copy()
        for key in (
            "SLURM_JOB_ID",
            "ISLANDS_STORAGE_ROOT",
            "ISLANDS_SLURM_LOG_DIR",
            "ATHENA_STUDY_CANARY_ROOT",
            "ATHENA_STUDY_RUN_ROOT",
            "ATHENA_STUDY_CANARY_JOB_ID",
            "ATHENA_FROZEN_RUN_ROOT",
            "ATHENA_FROZEN_ARRAY",
            "ATHENA_STUDY_REPEAT",
        ):
            self.env.pop(key, None)
        self.env.update(
            MOCK_BIN=bash_path(bin_dir),
            MOCK_CAPTURE=bash_path(self.capture),
            ISLANDS_VENV_DIR=bash_path(venv_bin.parent),
            SCRATCH=bash_path(self.root / "scratch"),
        )

    @staticmethod
    def write_executable(path, text):
        path.write_bytes(text.encode("utf-8"))
        path.chmod(0o755)

    def submit(self, arguments, extra_env=None, script="submit_study.sh"):
        env = dict(self.env)
        if extra_env:
            env.update(extra_env)
        env["SUBMITTER"] = bash_path(self.scripts / script)
        env["ARGS"] = arguments
        return subprocess.run(
            [
                self.bash,
                "-c",
                'export PATH="$MOCK_BIN:$PATH"; exec bash "$SUBMITTER" $ARGS',
            ],
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=30,
        )

    def test_canary_is_one_bounded_manual_job(self):
        result = self.submit("--canary")
        self.assertEqual(0, result.returncode, result.stderr)
        arguments = self.capture.read_text(encoding="utf-8").splitlines()
        for value in (
            "--nodes=1",
            "--cpus-per-task=16",
            "--gres=gpu:1",
            "--time=00:15:00",
            "--account=plgintobl-gpu-a100",
        ):
            self.assertIn(value, arguments)
        self.assertIn("ATHENA_STUDY_MODE=canary", "\n".join(arguments))
        self.assertIn("MAX_GPU_HOURS=0.25", result.stdout)
        self.assertIn("No automatic retry", result.stdout)

    def test_full_requires_passed_same_commit_canary_and_explicit_cost_gate(self):
        missing_gate = self.submit("--full")
        self.assertNotEqual(0, missing_gate.returncode)

        canary_root = self.root / "scratch" / "islandsEA" / "results" / "athena_study_canaries"
        validation = canary_root / "123" / "validation.json"
        validation.parent.mkdir(parents=True)
        validation.write_text('{}\n', encoding="utf-8")
        result = self.submit(
            "--full --confirm-one-of-1800-max-2-gpuh",
            {"ATHENA_STUDY_CANARY_JOB_ID": "123"},
        )
        self.assertEqual(0, result.returncode, result.stderr)
        arguments = self.capture.read_text(encoding="utf-8").splitlines()
        self.assertIn("--time=02:00:00", arguments)
        self.assertIn("ATHENA_STUDY_MODE=full", "\n".join(arguments))
        self.assertIn("MAX_GPU_HOURS=2.0", result.stdout)

    def test_dirty_checkout_never_submits(self):
        result = self.submit("--canary", {"MOCK_DIRTY": "1"})
        self.assertNotEqual(0, result.returncode)
        self.assertFalse(self.capture.exists())

    def test_frozen_three_repeat_array_submits_directly(self):
        result = self.submit(
            "",
            {
                "ATHENA_EXPECTED_COMMIT": "stale-commit-from-login-shell",
                "ATHENA_STUDY_CANARY_JOB_ID": "999",
            },
            script="submit_frozen_torus3.sh",
        )
        self.assertEqual(0, result.returncode, result.stderr)
        arguments = self.capture.read_text(encoding="utf-8").splitlines()
        for value in (
            "--array=1-3%3",
            "--nodes=1",
            "--cpus-per-task=16",
            "--gres=gpu:1",
            "--time=02:00:00",
            "--account=plgintobl-gpu-a100",
        ):
            self.assertIn(value, arguments)
        exported = "\n".join(arguments)
        self.assertIn("ATHENA_STUDY_MODE=full", exported)
        self.assertIn("ATHENA_FROZEN_ARRAY=1", exported)
        self.assertNotIn("ATHENA_STUDY_CANARY_JOB_ID", exported)
        self.assertNotIn("ATHENA_EXPECTED_COMMIT", exported)
        self.assertIn("ATHENA_FROZEN_REPEATS=1,2,3", result.stdout)
        self.assertIn("MAX_TOTAL_GPU_HOURS=6.0", result.stdout)
        self.assertIn("No automatic retry", result.stdout)

    def test_frozen_three_repeat_array_does_not_gate_on_dirty_checkout(self):
        result = self.submit(
            "",
            {"MOCK_DIRTY": "1"},
            script="submit_frozen_torus3.sh",
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue(self.capture.exists())

    def test_job_wrapper_has_valid_bash_syntax(self):
        for script in ("run_study_job.sh", "submit_frozen_torus3.sh"):
            with self.subTest(script=script):
                result = subprocess.run(
                    [self.bash, "-n", str(self.scripts / script)],
                    text=True,
                    capture_output=True,
                    timeout=30,
                )
                self.assertEqual(0, result.returncode, result.stderr)

    def test_job_wrapper_forwards_repeat_to_runner_and_validator(self):
        script = (self.scripts / "run_study_job.sh").read_text(encoding="utf-8")
        self.assertIn('--repeat "$STUDY_REPEAT"', script)
        self.assertIn('--expected-repeat "$STUDY_REPEAT"', script)
        self.assertIn('STUDY_REPEAT="$SLURM_ARRAY_TASK_ID"', script)
        for argument in (
            "--problem r01_elliptic",
            "--dimension 200",
            "--islands 144",
            "--evaluations 8000",
            "--population 16",
            "--offspring 4",
            "--migrants 5",
            "--interval 5",
            "--torus-rows 12",
            "--torus-columns 12",
            "--topology torus",
            "--strategy best",
            "--acceptance plain",
            "--seed 20260912",
            "--instance-seed 20260511",
        ):
            self.assertIn(argument, script)


if __name__ == "__main__":
    unittest.main()
