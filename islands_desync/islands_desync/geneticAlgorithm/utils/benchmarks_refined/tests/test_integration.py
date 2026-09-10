import contextlib
import io
import json
import math
import os
from pathlib import Path
import pickle
import random
import shutil
import tempfile
import unittest
from unittest.mock import patch

from jmetal.algorithm.singleobjective.genetic_algorithm import GeneticAlgorithm
from jmetal.core.problem import BinaryProblem
from jmetal.operator import BinaryTournamentSelection, BitFlipMutation, SPXCrossover
from jmetal.util.termination_criterion import StoppingByEvaluations

from islands_desync.geneticAlgorithm.utils import benchmark_problems as legacy
from islands_desync.geneticAlgorithm.utils.benchmarks_refined import (
    BENCHMARKS, CONTINUOUS_BENCHMARKS, DISCRETE_BENCHMARKS, create_problem,
)
from islands_desync.geneticAlgorithm.utils.myDefCrossover import SwitchCrossover
from islands_desync.geneticAlgorithm.utils.myDefMutation import MyUniformMutation


class JMetalIntegrationTests(unittest.TestCase):
    def test_catalog_registration_and_log_prefixes(self):
        self.assertEqual(40, len(BENCHMARKS))
        self.assertEqual((30, 10), (len(CONTINUOUS_BENCHMARKS), len(DISCRETE_BENCHMARKS)))
        historical = legacy.CONTINUOUS_40_BENCHMARKS + legacy.DISCRETE_40_BENCHMARKS + legacy.GEATBX_OPTIONAL_BENCHMARKS
        prefixes = [name[:4] for name in list(BENCHMARKS) + historical]
        self.assertEqual(len(prefixes), len(set(prefixes)))
        for name in BENCHMARKS:
            problem = legacy.create_problem(name, 30 if name in CONTINUOUS_BENCHMARKS else 60)
            self.assertEqual(name, problem.get_name())
            self.assertTrue(legacy.is_registered_problem(name))
        self.assertEqual("c01_elliptic", legacy.create_problem("c01_elliptic", 30).get_name())

    def test_binary_legacy_parity(self):
        rng = random.Random(751)
        for new_name, old_name in zip(DISCRETE_BENCHMARKS, legacy.DISCRETE_40_BENCHMARKS):
            refined = create_problem(new_name, 60)
            old = legacy.create_problem(old_name, 60)
            for _ in range(20):
                bits = [bool(rng.randrange(2)) for _ in range(60)]
                a, b = refined.create_solution(), old.create_solution()
                a.variables[0], b.variables[0] = bits[:], bits[:]
                self.assertEqual(old.evaluate(b).objectives[0], refined.evaluate(a).objectives[0], new_name)

    def test_all_problems_run_in_jmetal_ga(self):
        # Each of all forty adapters exercises initialization, evaluation,
        # selection, mutation, crossover, replacement and termination.
        for name in BENCHMARKS:
            with self.subTest(name=name):
                problem = create_problem(name)
                binary = isinstance(problem, BinaryProblem)
                algorithm = GeneticAlgorithm(
                    problem=problem, population_size=8, offspring_population_size=4,
                    mutation=BitFlipMutation(1 / problem.number_of_bits) if binary else MyUniformMutation(1 / problem.number_of_variables, 10.),
                    crossover=SPXCrossover(1.) if binary else SwitchCrossover(),
                    selection=BinaryTournamentSelection(), termination_criterion=StoppingByEvaluations(24),
                )
                algorithm.run()
                self.assertEqual(24, algorithm.evaluations)
                self.assertEqual(8, len(algorithm.solutions))
                self.assertTrue(math.isfinite(algorithm.get_result().objectives[0]))
                metadata = problem.benchmark_metadata()
                self.assertEqual(metadata, json.loads(json.dumps(metadata, allow_nan=False)))
                self.assertEqual(64, len(metadata["implementation_sha256"]))
                restored = pickle.loads(pickle.dumps(problem))
                solution = problem.create_solution()
                expected = problem.evaluate(solution).objectives[0]
                solution.objectives[0] = float("nan")
                self.assertEqual(expected, restored.evaluate(solution).objectives[0])

    def test_active_builder_reaches_island_step_and_writes_provenance(self):
        from islands_desync.geneticAlgorithm.run_hpc.create_algorithm_hpc import create_algorithm_hpc
        from islands_desync.geneticAlgorithm.run_hpc.run_algorithm_params import RunAlgorithmParams
        ga_root = Path(create_algorithm_hpc.__code__.co_filename).resolve().parents[1]

        class LocalMigration:
            # No Ray actors/communication: this tests the actual builder and GA
            # step with one island, not distributed timing or SLURM scheduling.
            def wait_for_all_start(self):
                pass

            def start_time_measure(self):
                pass

        original_cwd = Path.cwd()
        for name in ("r29_composition7", "b03_nk_k4"):
            with tempfile.TemporaryDirectory(prefix="refined-builder-") as temporary:
                root = Path(temporary)
                config_dir = root / "islands_desync/geneticAlgorithm/algorithm/configurations"
                config_dir.mkdir(parents=True)
                shutil.copyfile(ga_root / "algorithm/configurations/algorithm_configuration.json", config_dir / "algorithm_configuration.json")
                shutil.copyfile(ga_root / "run_algorithm.py", root / "islands_desync/geneticAlgorithm/run_algorithm.py")
                params = RunAlgorithmParams(1, 2, 20, "refined_test", "000001", 1, "ring", "random", "plain")
                env = {"ISLANDS_PROBLEM": name, "ISLANDS_NUMBER_OF_VARIABLES": "30" if name.startswith("r") else "60",
                       "ISLANDS_NUMBER_OF_EVALUATIONS": "64", "ISLANDS_POPULATION_SIZE": "16", "ISLANDS_OFFSPRING_POPULATION_SIZE": "4"}
                algorithm = None
                try:
                    os.chdir(root)
                    with patch.dict(os.environ, env), contextlib.redirect_stdout(io.StringIO()):
                        algorithm = create_algorithm_hpc(0, LocalMigration(), params)
                        algorithm.solutions = algorithm.evaluate(algorithm.create_initial_solutions())
                        algorithm.init_progress()
                        algorithm.step()
                        algorithm.update_progress()
                    self.assertEqual(1, algorithm.step_num)
                    self.assertEqual(20, algorithm.evaluations)
                    run = Path(algorithm.path)
                    manifest = json.loads((run / "benchmark_manifest.json").read_text())
                    self.assertEqual(name, manifest["name"])
                    self.assertEqual(name, json.loads((run / "param.json").read_text())["problem"])
                finally:
                    # The legacy logger normally closes these at run end;
                    # this test intentionally stops after the first step.
                    if algorithm is not None:
                        for attribute in ("resultfile", "winnerfile"):
                            getattr(algorithm, attribute).fileSB.close()
                    os.chdir(original_cwd)
