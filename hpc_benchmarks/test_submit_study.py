"""Submission ordering/resource regression tests with fake tools, never SLURM."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class SubmissionTests(unittest.TestCase):
    def setUp(self):
        self.bash = "C:/Program Files/Git/bin/bash.exe" if os.name == "nt" else shutil.which("bash")
        if not self.bash or not Path(self.bash).is_file():
            self.skipTest("Bash required")
        self.project = Path(__file__).resolve().parents[1]
        scratch = self.project / "tmp" / "study_submit_tests"
        scratch.mkdir(parents=True, exist_ok=True)
        temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.venv = self.root / "venv"
        (self.venv / "bin").mkdir(parents=True)
        self.script(self.bin / "git", '#!/usr/bin/env bash\necho "${MOCK_BRANCH:-summer_benchmarks_ares}"\n')
        self.script(self.bin / "module", '#!/usr/bin/env bash\nexit 0\n')
        self.script(self.bin / "sbatch", '#!/usr/bin/env bash\nprintf "%s\\n" "$@" > "$TEST_ROOT/submitted"\necho 12345\n')
        self.script(self.venv / "bin/python", '''#!/usr/bin/env bash
if [[ "$1" == "-c" ]]; then echo "${MOCK_ISLANDS:-144}"; exit 0; fi
printf '%s\n' "$@" > "$TEST_ROOT/preflight_args"
[[ "${MOCK_REJECT:-0}" == "0" ]] || { echo "Selected graph failed integrity validation" >&2; exit 2; }
printf '{"islands": %s}\n' "${MOCK_ISLANDS:-144}"
''')
        self.env = os.environ.copy()
        for key in tuple(self.env):
            if key.startswith("ISLANDS_") or key.startswith("SLURM_"):
                del self.env[key]
        self.env.update(TEST_ROOT=self.root.as_posix(), SCRATCH=(self.root / "scratch").as_posix(), ISLANDS_VENV_DIR=self.venv.as_posix())

    def script(self, path, text):
        path.write_text(text, encoding="utf-8", newline="\n")
        path.chmod(0o755)

    def invoke(self, name, *args, **overrides):
        env = {**self.env, **overrides}
        bin_path = self.bin.as_posix()
        if os.name == "nt":
            bin_path = "/" + bin_path[0].lower() + bin_path[2:]
        return subprocess.run([self.bash, "-c", 'export PATH="$1:$PATH"; shift; exec bash "$@"',
                               "study-test", bin_path,
                               (self.project / "hpc_benchmarks" / name).as_posix(), *args],
                              env=env, cwd=self.project, text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=20)

    def test_rejected_graph_never_reaches_sbatch(self):
        result = self.invoke("submit_ares_144.sh", "--topology", "er4", MOCK_REJECT="1")
        self.assertNotEqual(0, result.returncode)
        self.assertTrue((self.root / "preflight_args").exists(), result.stderr)
        self.assertFalse((self.root / "submitted").exists())

    def test_fixed_profile_pins_count_in_preflight_and_selects_144_job(self):
        result = self.invoke("submit_ares_144.sh", "--islands", "200", "--topology", "ba")
        self.assertEqual(0, result.returncode, result.stderr)
        args = (self.root / "preflight_args").read_text().splitlines()
        self.assertEqual(["--islands", "144", "--dry-run"], args[-3:])
        submitted = (self.root / "submitted").read_text()
        self.assertIn("run_ares_144.sh", submitted)
        self.assertIn("benchmark-144-", submitted)

    def test_small_explicit_diagnostic_uses_small_allocation(self):
        result = self.invoke("submit_ares.sh", "--diagnostic", "--islands", "2", MOCK_ISLANDS="2")
        self.assertEqual(0, result.returncode, result.stderr)
        submitted = (self.root / "submitted").read_text()
        self.assertIn("--nodes=1", submitted)
        self.assertIn("--cpus-per-task=6", submitted)

    def test_gpu_checkout_cannot_submit_cpu_profile(self):
        result = self.invoke("submit_ares_144.sh", MOCK_BRANCH="summer_benchmarks_athena")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("Ares CPU checkout", result.stderr)
        self.assertFalse((self.root / "submitted").exists())

    def test_old_200_profile_fails_without_submission(self):
        result = self.invoke("submit_ares_200.sh")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("retired", result.stderr)
        self.assertFalse((self.root / "submitted").exists())


if __name__ == "__main__":
    unittest.main()
