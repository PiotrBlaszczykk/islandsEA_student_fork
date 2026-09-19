"""Real post-run shell helper and existing analysis reader, using small fixtures."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'hpc_benchmarks'))
sys.path.insert(0, str(ROOT / 'islands_desync'))
import test_run_bundle as fixtures
import run_bundle


class BundleIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.BundleTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def test_existing_analysis_reader_locates_portable_telemetry(self):
        spec = importlib.util.spec_from_file_location('bundle_analysis', ROOT / 'islands_desync/analyze_migration_delays.py')
        analyzer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(analyzer)
        destination = Path(self.fixture.export()['directory'])
        self.assertEqual(destination / 'results', analyzer.portable_results(destination))
        self.assertTrue(analyzer.research_metrics_available(destination / 'results'))
        original = analyzer.load_research_fitness_histories(self.fixture.raw)
        portable = analyzer.load_research_fitness_histories(destination / 'results')
        self.assertEqual(original, portable)
        self.assertEqual({0, 1}, set(portable))

    def invoke_shell(self, status):
        bash = 'C:/Program Files/Git/bin/bash.exe' if os.name == 'nt' else shutil.which('bash')
        if not bash or not Path(bash).is_file():
            self.skipTest('Bash not available')
        fixture = self.fixture
        venv = fixture.root / 'venv'
        (venv / 'bin').mkdir(parents=True)
        python = venv / 'bin/python'
        python.write_text('#!/usr/bin/env bash\nexec "$TEST_PYTHON" "$@"\n', newline='\n')
        python.chmod(0o755)
        env = {key: value for key, value in os.environ.items() if not key.startswith(('ISLANDS_', 'SLURM_'))}
        env.update(TEST_PYTHON=sys.executable, PROJECT_DIR=ROOT.as_posix(), VENV_DIR=venv.as_posix(),
                   SLURM_JOB_ID='123', ISLANDS_STORAGE_ROOT=(fixture.root / 'storage').as_posix(),
                   ISLANDS_RESULTS_ROOT=(fixture.root / 'storage/results').as_posix(),
                   ISLANDS_SLURM_LOG_DIR=fixture.logs.as_posix(),
                   TEST_POINTER=(fixture.job / 'result_pointer.json').as_posix(), TEST_EXIT=str(status))
        script = '''source "$PROJECT_DIR/hpc_benchmarks/run_bundle.sh"
islandsea_bundle_prepare ares --result-pointer "$TEST_POINTER"
trap islandsea_bundle_early_exit EXIT
exit "$TEST_EXIT"
'''
        return subprocess.run([bash, '-c', script], env=env, capture_output=True, text=True, timeout=30)

    def test_shell_helper_creates_verified_archive_with_explicit_pointer(self):
        result = self.invoke_shell(0)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn('RUN_BUNDLE_ARCHIVE=', result.stdout)
        archive = self.fixture.root / 'storage/exports/run_123.tar.gz'
        self.assertTrue(run_bundle.verify_archive(archive)['complete'])

    def test_shell_failure_preserves_original_exit_code_and_partial_payload(self):
        (self.fixture.raw / 'metrics/island_001/runtime.json').unlink()
        result = self.invoke_shell(7)
        self.assertEqual(7, result.returncode, result.stderr)
        record = run_bundle.read_json(self.fixture.root / 'storage/exports/run_123/results/bundle_manifest.json')
        self.assertFalse(record['complete'])
        self.assertEqual(7, record['job_exit_code'])


if __name__ == '__main__':
    unittest.main()
