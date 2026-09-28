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
printf '%s\n' "$@" >> "$MOCK_CAPTURE"
printf 'sbatch\n' >> "$MOCK_CALLS"
if [[ "$*" == *"--dependency=afterany:7654321"* ]]; then
    echo 7654322
else
    echo 7654321
fi
''',
        )
        # The Codex Windows sandbox grants native Python access to the
        # workspace but MSYS mkdir runs under a different ACL view. Directory
        # creation is not the behaviour under test; path guards and the exact
        # captured sbatch arguments are.
        self.write_executable(bin_dir / "mkdir", "#!/usr/bin/env bash\nexit 0\n")
        self.write_executable(bin_dir / "module", "#!/usr/bin/env bash\nexit 0\n")
        self.write_executable(
            bin_dir / "scontrol",
            "#!/usr/bin/env bash\nprintf 'scontrol %s\\n' \"$*\" >> \"$MOCK_CALLS\"\n",
        )
        venv_bin = self.root / "venv" / "bin"
        venv_bin.mkdir(parents=True)
        self.write_executable(
            venv_bin / "python",
            "#!/usr/bin/env bash\nprintf '%s\\n' \"$*\" >> \"$MOCK_PYTHON_CAPTURE\"\nexit 0\n",
        )
        self.capture = self.root / "submission.txt"
        self.calls = self.root / "calls.txt"
        self.python_capture = self.root / "python.txt"
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
            "ATHENA_PRODUCTION_ER4_BEST",
            "ATHENA_PRODUCTION_ER4_RANDOM",
            "ATHENA_PRODUCTION_ER4_MAXDISTANCE",
            "ATHENA_STUDY_REPEAT",
        ):
            self.env.pop(key, None)
        self.env.update(
            MOCK_BIN=bash_path(bin_dir),
            MOCK_CAPTURE=bash_path(self.capture),
            MOCK_CALLS=bash_path(self.calls),
            MOCK_PYTHON_CAPTURE=bash_path(self.python_capture),
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

    def test_er4_best_production_submits_gpu_array_and_cpu_afterany_finalizer(self):
        plan = self.root / "scratch" / "islandsEA" / "campaigns" / "er4_best_7654321" / "campaign_plan.json"
        plan.parent.mkdir(parents=True)
        plan.write_text("{}\n", encoding="utf-8")
        result = self.submit(
            "",
            {"ATHENA_EXPECTED_COMMIT": "stale", "ATHENA_STUDY_CANARY_JOB_ID": "999",
             "ATHENA_FINALIZER_PARTITION": "plgrid",
             "ATHENA_FINALIZER_ACCOUNT": "plgintobl-cpu"},
            script="submit_production_er4_best_120.sh",
        )
        self.assertEqual(0, result.returncode, result.stderr)
        arguments = self.capture.read_text(encoding="utf-8").splitlines()
        for value in (
            "--array=1-120%3", "--nodes=1", "--cpus-per-task=16",
            "--gres=gpu:1", "--time=02:00:00",
            "--account=plgintobl-gpu-a100",
        ):
            self.assertIn(value, arguments)
        exported = "\n".join(arguments)
        self.assertIn("ATHENA_PRODUCTION_ER4_BEST=1", exported)
        self.assertNotIn("ATHENA_EXPECTED_COMMIT", exported)
        self.assertNotIn("ATHENA_STUDY_CANARY_JOB_ID", exported)
        self.assertIn("MAX_TOTAL_GPU_HOURS=240.0", result.stdout)
        self.assertIn("No automatic retry", result.stdout)
        self.assertEqual(["sbatch", "sbatch"], self.calls.read_text(encoding="utf-8").splitlines())
        self.assertIn("--dependency=afterany:7654321", arguments)
        self.assertIn("--partition=plgrid", arguments)
        self.assertIn("--account=plgintobl-cpu", arguments)
        submissions = [i for i, argument in enumerate(arguments) if argument == "--parsable"]
        self.assertEqual(2, len(submissions))
        self.assertNotIn("--gres=gpu:1", arguments[submissions[1]:])
        self.assertIn("ATHENA_ER4_BEST_FINALIZER_JOB_ID=7654322", result.stdout)
        invoked = self.python_capture.read_text(encoding="utf-8")
        self.assertIn("production_er4_best.py --check", invoked)
        self.assertIn("campaign_er4_best.py plan", invoked)

    def test_er4_best_requires_explicit_cpu_finalizer_resources_before_gpu_submit(self):
        result = self.submit("", script="submit_production_er4_best_120.sh")
        self.assertNotEqual(0, result.returncode)
        self.assertFalse(self.calls.exists())
        gpu_only = self.submit(
            "", {"ATHENA_FINALIZER_PARTITION": "plgrid-gpu-a100",
                 "ATHENA_FINALIZER_ACCOUNT": "plgintobl-gpu-a100"},
            script="submit_production_er4_best_120.sh",
        )
        self.assertNotEqual(0, gpu_only.returncode)
        self.assertFalse(self.calls.exists())

    def test_er4_random_submits_one_held_array_then_releases_after_plan(self):
        result = self.submit("", script="submit_production_er4_random_120.sh")
        self.assertEqual(0, result.returncode, result.stderr)
        arguments = self.capture.read_text(encoding="utf-8").splitlines()
        for value in ("--array=1-120%3", "--hold", "--nodes=1", "--cpus-per-task=16",
                      "--gres=gpu:1", "--time=02:00:00", "--account=plgintobl-gpu-a100"):
            self.assertIn(value, arguments)
        exported = "\n".join(arguments)
        self.assertIn("ATHENA_PRODUCTION_ER4_RANDOM=1", exported)
        self.assertNotIn("ATHENA_PRODUCTION_ER4_BEST", exported)
        self.assertNotIn("ATHENA_EXPECTED_COMMIT", exported)
        self.assertEqual(["sbatch", "scontrol release 7654321"],
                         self.calls.read_text(encoding="utf-8").splitlines())
        self.assertIn("production_er4_best.py --check --strategy random",
                      self.python_capture.read_text(encoding="utf-8"))
        self.assertIn("campaign_er4_best.py plan --strategy random",
                      self.python_capture.read_text(encoding="utf-8"))
        self.assertIn("ATHENA_ER4_RANDOM_ARRAY_JOB_ID=7654321", result.stdout)
        self.assertIn("No automatic retry, resubmission, or follow-up job", result.stdout)

    def test_er4_maxdistance_submits_only_one_held_gpu_array(self):
        result = self.submit("", script="submit_production_er4_maxdistance_120.sh")
        self.assertEqual(0, result.returncode, result.stderr)
        arguments = self.capture.read_text(encoding="utf-8").splitlines()
        for value in ("--array=1-120%3", "--hold", "--cpus-per-task=16",
                      "--gres=gpu:1", "--time=02:00:00", "--account=plgintobl-gpu-a100"):
            self.assertIn(value, arguments)
        exported = "\n".join(arguments)
        self.assertIn("ATHENA_PRODUCTION_ER4_MAXDISTANCE=1", exported)
        self.assertNotIn("ATHENA_PRODUCTION_ER4_RANDOM", exported)
        self.assertNotIn("ATHENA_PRODUCTION_ER4_BEST", exported)
        self.assertNotIn("ATHENA_EXPECTED_COMMIT", exported)
        self.assertEqual(["sbatch", "scontrol release 7654321"],
                         self.calls.read_text(encoding="utf-8").splitlines())
        invoked = self.python_capture.read_text(encoding="utf-8")
        self.assertIn("production_er4_best.py --check --strategy maxDistance", invoked)
        self.assertIn("campaign_er4_best.py plan --strategy maxDistance", invoked)
        self.assertIn("ATHENA_ER4_MAXDISTANCE_ARRAY_JOB_ID=7654321", result.stdout)
        self.assertIn("No automatic retry, resubmission, or follow-up job", result.stdout)

    def test_existing_array_submits_only_cpu_finalizer_without_dependency(self):
        plan = self.root / "scratch" / "islandsEA" / "campaigns" / "er4_best_7654321" / "campaign_plan.json"
        plan.parent.mkdir(parents=True)
        plan.write_text("{}\n", encoding="utf-8")
        result = self.submit(
            "--existing 7654321",
            {"ATHENA_FINALIZER_PARTITION": "plgrid",
             "ATHENA_FINALIZER_ACCOUNT": "plgintobl-cpu"},
            script="submit_finalize_production_er4_best_120.sh",
        )
        self.assertEqual(0, result.returncode, result.stderr)
        arguments = self.capture.read_text(encoding="utf-8").splitlines()
        self.assertNotIn("--gres=gpu:1", arguments)
        self.assertFalse(any(argument.startswith("--dependency=") for argument in arguments))
        self.assertIn("run_finalize_production_er4_best_120.sh", "\n".join(arguments))
        self.assertEqual(["sbatch"], self.calls.read_text(encoding="utf-8").splitlines())

    def test_job_wrapper_has_valid_bash_syntax(self):
        for script in ("run_study_job.sh", "submit_frozen_torus3.sh",
                       "submit_production_er4_best_120.sh",
                       "submit_production_er4_random_120.sh",
                       "submit_production_er4_maxdistance_120.sh",
                       "submit_finalize_production_er4_best_120.sh",
                       "run_finalize_production_er4_best_120.sh"):
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
            "STUDY_PROBLEM=r01_elliptic",
            "--dimension 200",
            "--islands 144",
            "--evaluations 8000",
            "--population 16",
            "--offspring 4",
            "--migrants 5",
            "--interval 5",
            "--torus-rows 12",
            "--torus-columns 12",
            "STUDY_TOPOLOGY=torus",
            "STUDY_STRATEGY=best",
            '--strategy "$STUDY_STRATEGY"',
            '--expected-strategy "$STUDY_STRATEGY"',
            "--acceptance plain",
            "--seed 20260912",
            "--instance-seed 20260511",
        ):
            self.assertIn(argument, script)


if __name__ == "__main__":
    unittest.main()
