"""Regression tests for SLURM's copied /var/spool/slurmd batch scripts.

Copies of every pilot batch stage are executed from a spool-shaped directory.
Cluster commands are replaced with local fakes, so these tests never submit a
job, start Ray, or run a benchmark.
"""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class PilotSpoolPathTests(unittest.TestCase):
    BATCH_CASES = {
        "run_pilot_canary.sh": (),
        "continue_after_canary.sh": ("123",),
        "run_pilot_array.sh": (),
        "finalize_pilot.sh": ("456",),
    }
    SUBMITTERS = {
        "submit_canary.sh": 1,
        "launch_pilot.sh": 1,
        "submit_pilot.sh": 2,
    }

    def setUp(self):
        candidate = Path("C:/Program Files/Git/bin/bash.exe")
        self.bash = str(candidate) if os.name == "nt" else shutil.which("bash")
        if not self.bash or not Path(self.bash).is_file():
            self.skipTest("Bash required")

        self.project = Path(__file__).resolve().parents[1]
        scratch = self.project / "tmp" / "pilot_spool_tests"
        scratch.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.venv = self.root / "venv"
        (self.venv / "bin").mkdir(parents=True)

        self._script(
            self.venv / "bin" / "python",
            """#!/bin/bash
printf 'MOCK_PYTHON_CALL=%s\n' "$*" >&2
if [[ " $* " == *"importlib.metadata"* ]]; then
  printf '%s\n' 'ray=2.9.3 click=8.2.1'
elif [[ " $* " == *" benchmark-args "* ]]; then
  printf '%s\n' --problem r01_elliptic --dimension 200
elif [[ " $* " == *"hpc_benchmarks/run_benchmark.py"* && " $* " == *" --dry-run "* ]]; then
  printf '%s\n' '{"islands":144,"dimension":200,"evaluations":128,"required_ray_cpus":289,"required_slurm_cpus":290,"topology":"torus","strategy":"best","acceptance":"plain"}'
fi
exit 0
""",
        )
        self._script(
            self.venv / "bin" / "ray",
            """#!/bin/bash
if [[ "${MOCK_RAY_FAIL:-0}" == 1 ]]; then
  printf '%s\n' 'ValueError: object is not a valid Sentinel' >&2
  exit 1
fi
printf '%s\n' 'ray, version 2.9.3'
""",
        )
        self._script(self.venv / "bin" / "activate", "# test activation\n")
        self.mock_env = self.root / "mock_bash_env.sh"
        self._script(
            self.mock_env,
            """#!/bin/bash
git() {
  case "$*" in
    "rev-parse HEAD") printf '%s\n' "test-commit" ;;
    "status --porcelain --untracked-files=all") ;;
    "status --short") ;;
    "branch --show-current") printf '%s\n' "summer_benchmarks_ares" ;;
    *) printf 'unexpected git invocation: %s\n' "$*" >&2; return 2 ;;
  esac
}
module() { return 0; }
mkdir() { return 0; }
sacct() { printf '%s\n' '123|COMPLETED|0:0'; }
sbatch() {
  printf 'MOCK_SBATCH_ARGS=%s\n' "$*" >&2
  printf '%s\n' '12345'
}
bash() {
  printf 'MOCK_BASH_CALL=%s\n' "$*"
  case "$1" in
    */pilot_run/submit_pilot.sh)
      printf '%s\n' 'PILOT_ARRAY_JOB_ID=456' 'PILOT_FINALIZER_JOB_ID=789'
      ;;
  esac
  return 0
}
export -f git module mkdir sacct sbatch bash
""",
        )

        spool = self.root / "var" / "spool" / "slurmd" / "job999"
        spool.mkdir(parents=True)
        self.spool = spool

        self.shell_storage = (
            f"/tmp/islandsea-pilot-spool-{os.getpid()}-{self.root.name}"
        )
        storage_setup = subprocess.run(
            [
                self.bash,
                "-c",
                f'/usr/bin/mkdir -p "{self.shell_storage}/results/pilot_runs/pilot_canaries/123" '
                f'"{self.shell_storage}/results/pilot_runs/456/repeat-1"',
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, storage_setup.returncode, storage_setup.stderr)
        self.addCleanup(self._cleanup_shell_storage)

        artifacts = f"{self.shell_storage}/results/pilot_runs"

        self.env = os.environ.copy()
        for key in tuple(self.env):
            if key.startswith("ISLANDS_") or key.startswith("SLURM_"):
                del self.env[key]
        self.env.update(
            {
                "MSYS2_ARG_CONV_EXCL": "*",
                "MSYS2_ENV_CONV_EXCL": "*",
                "BASH_ENV": self._shell_path(self.mock_env),
                "USER": "pilot-spool-test",
                "SCRATCH": self.shell_storage,
                "ISLANDS_PROJECT_DIR": self._shell_path(self.project),
                "ISLANDS_VENV_DIR": self._shell_path(self.venv),
                "ISLANDS_STORAGE_ROOT": self.shell_storage,
                "ISLANDS_RESULTS_ROOT": f"{self.shell_storage}/results",
                "ISLANDS_LOG_ROOT": f"{self.shell_storage}/logs",
                "ISLANDS_ARTIFACT_ROOT": artifacts,
                "ISLANDS_SLURM_LOG_DIR": f"{self.shell_storage}/logs/slurm",
                "ISLANDS_RAY_FAILURE_ROOT": f"{self.shell_storage}/logs/ray_failures",
                "ISLANDS_CHECKPOINT_ROOT": f"{self.shell_storage}/checkpoints",
                "ISLANDS_TMP_ROOT": f"{self.shell_storage}/tmp",
                "SLURM_SUBMIT_DIR": self._shell_path(self.spool),
                "SLURM_JOB_ID": "999",
                "SLURM_ARRAY_JOB_ID": "456",
                "SLURM_ARRAY_TASK_ID": "1",
                "PILOT_EXPECTED_COMMIT": "test-commit",
            }
        )

    def _cleanup_shell_storage(self):
        if self.shell_storage.startswith("/tmp/islandsea-pilot-spool-"):
            subprocess.run(
                [self.bash, "-c", f'/usr/bin/rm -rf -- "{self.shell_storage}"'],
                capture_output=True,
                check=False,
            )

    @staticmethod
    def _shell_path(path):
        value = str(Path(path).resolve()).replace("\\", "/")
        if os.name == "nt":
            return f"/{value[0].lower()}{value[2:]}"
        return value

    @staticmethod
    def _script(path, content):
        path.write_text(content, encoding="utf-8", newline="\n")
        path.chmod(0o755)

    def _invoke_spool_copy(self, script_name, args=(), **overrides):
        copied = self.spool / f"{script_name}.slurm_script"
        shutil.copy2(self.project / "pilot_run" / script_name, copied)
        return self._invoke_script(copied, args, self.spool, **overrides)

    def _invoke_script(self, script, args=(), cwd=None, **overrides):
        env = {**self.env, **overrides}
        return subprocess.run(
            [
                self.bash,
                "-c",
                'export PATH="/usr/bin:/bin"; exec "$@"',
                "pilot-spool-test",
                self._shell_path(self.bash),
                self._shell_path(script),
                *args,
            ],
            cwd=cwd or self.project,
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=20,
        )

    def test_canary_only_submitter_exports_checkout_and_does_not_schedule_gate(self):
        result = self._invoke_script(
            self.project / "pilot_run" / "submit_canary.sh"
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(1, result.stderr.count("MOCK_SBATCH_ARGS="))
        self.assertIn(
            f"ISLANDS_PROJECT_DIR={self._shell_path(self.project)}",
            result.stderr,
        )
        self.assertIn("run_pilot_canary.sh", result.stderr)
        self.assertIn("RAY_CLI_PREFLIGHT_OK ray, version 2.9.3", result.stdout)
        self.assertNotIn("continue_after_canary.sh", result.stderr)
        self.assertNotIn("run_pilot_array.sh", result.stderr)
        self.assertNotIn("finalize_pilot.sh", result.stderr)

    def test_canary_submitter_blocks_sbatch_when_ray_cli_import_fails(self):
        result = self._invoke_script(
            self.project / "pilot_run" / "submit_canary.sh",
            MOCK_RAY_FAIL="1",
        )
        self.assertNotEqual(0, result.returncode)
        self.assertIn("not a valid Sentinel", result.stderr)
        self.assertIn("Ray CLI preflight failed before submission", result.stderr)
        self.assertIn("click==8.2.1", result.stderr)
        self.assertNotIn("MOCK_SBATCH_ARGS=", result.stderr)

    def test_every_batch_stage_resolves_checkout_from_project_env_when_copied_to_spool(self):
        results = []
        for script_name, args in self.BATCH_CASES.items():
            with self.subTest(script=script_name):
                result = self._invoke_spool_copy(script_name, args)
                results.append(result)
                self.assertEqual(0, result.returncode, result.stderr)

        calls = "\n".join((result.stdout + result.stderr) for result in results)
        self.assertIn(self._shell_path(self.project), calls)
        self.assertNotIn(self._shell_path(self.spool) + "/pilot_run", calls)

    def test_every_batch_stage_rejects_missing_project_env_even_with_submit_dir(self):
        for script_name, args in self.BATCH_CASES.items():
            with self.subTest(script=script_name):
                result = self._invoke_spool_copy(
                    script_name, args, ISLANDS_PROJECT_DIR=""
                )
                self.assertNotEqual(0, result.returncode)
                self.assertIn("Missing absolute repository path", result.stderr)

    def test_batch_stage_rejects_relative_or_invalid_project_path(self):
        relative = self._invoke_spool_copy(
            "run_pilot_canary.sh", ISLANDS_PROJECT_DIR="relative/checkout"
        )
        self.assertNotEqual(0, relative.returncode)
        self.assertIn("must be an absolute path", relative.stderr)

        invalid = self._invoke_spool_copy(
            "run_pilot_canary.sh",
            ISLANDS_PROJECT_DIR=self._shell_path(self.root / "missing-checkout"),
        )
        self.assertNotEqual(0, invalid.returncode)
        self.assertIn("Invalid ISLANDS_PROJECT_DIR", invalid.stderr)

    def test_submitters_explicitly_export_absolute_project_dir_for_every_sbatch(self):
        for script_name, expected_sbatch_calls in self.SUBMITTERS.items():
            with self.subTest(script=script_name):
                content = (self.project / "pilot_run" / script_name).read_text(
                    encoding="utf-8"
                )
                self.assertEqual(expected_sbatch_calls, content.count("sbatch --parsable"))
                self.assertEqual(
                    expected_sbatch_calls,
                    content.count("ISLANDS_PROJECT_DIR=${PROJECT_DIR}"),
                )

    def test_pilot_submitters_run_ray_cli_preflight(self):
        for script_name in ("submit_canary.sh", "submit_pilot.sh"):
            with self.subTest(script=script_name):
                content = (self.project / "pilot_run" / script_name).read_text(
                    encoding="utf-8"
                )
                self.assertIn(
                    'source "$PROJECT_DIR/hpc_benchmarks/ray_cli_preflight.sh"',
                    content,
                )
                self.assertIn('islandsea_validate_ray_cli "$VENV_DIR"', content)


if __name__ == "__main__":
    unittest.main()
