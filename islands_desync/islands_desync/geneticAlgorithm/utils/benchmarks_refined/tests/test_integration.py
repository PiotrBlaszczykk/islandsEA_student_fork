import contextlib
import importlib.util
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

from islands_desync.geneticAlgorithm.run_hpc import benchmark_configuration as active
from islands_desync.geneticAlgorithm.utils.benchmarks_refined import (
    BENCHMARKS, CONTINUOUS_BENCHMARKS, DISCRETE_BENCHMARKS, create_problem,
)
from islands_desync.geneticAlgorithm.utils.myDefCrossover import SwitchCrossover
from islands_desync.geneticAlgorithm.utils.myDefMutation import MyUniformMutation


class JMetalIntegrationTests(unittest.TestCase):
    def test_hpc_preflight_validates_configurations_and_topologies(self):
        path = Path(__file__).resolve().parents[6] / "hpc_benchmarks/run_benchmark.py"
        spec = importlib.util.spec_from_file_location("hpc_benchmark_launcher_test", path)
        launcher = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(launcher)
        base = ["--problem", "r29_composition7", "--dimension", "200", "--islands", "180", "--topology", "torus"]
        args = launcher.parser().parse_args(base)
        with patch.dict(os.environ, launcher.environment(args)):
            configuration, problem, _, adjacency = launcher.validate(args)
        self.assertEqual(200, problem.number_of_variables)
        self.assertEqual(8000, configuration["number_of_evaluations"])
        self.assertEqual(180, len(adjacency))
        self.assertTrue(all(len(targets) == 4 for targets in adjacency.values()))
        for invalid in (["--dimension", "20"], ["--offspring", "3"], ["--evaluations", "17"],
                        ["--migrants", "17"], ["--islands", "150"], ["--acceptance", "typo"],
                        ["--islands", "2", "--topology", "er1"]):
            args = launcher.parser().parse_args(base + invalid)
            with self.subTest(invalid=invalid), patch.dict(os.environ, launcher.environment(args)), self.assertRaises(ValueError):
                launcher.validate(args)

    def test_catalog_registration_and_log_prefixes(self):
        self.assertEqual(40, len(BENCHMARKS))
        self.assertEqual((30, 10), (len(CONTINUOUS_BENCHMARKS), len(DISCRETE_BENCHMARKS)))
        historical = ["Sphere", "Rastrigin"]
        prefixes = [name[:4] for name in list(BENCHMARKS) + historical]
        self.assertEqual(len(prefixes), len(set(prefixes)))
        for name in BENCHMARKS:
            problem = active.create_problem(name, 30 if name in CONTINUOUS_BENCHMARKS else 60)
            self.assertEqual(name, problem.get_name())
            self.assertEqual(problem.evaluator.dimension, 30 if name in CONTINUOUS_BENCHMARKS else 60)
        self.assertEqual("Sphere", active.create_problem("sphere", 200).get_name())
        self.assertEqual("Rastrigin", active.create_problem("rastrigin", 200).get_name())

    def test_binary_distance_matches_bitwise_squared_distance(self):
        from islands_desync.geneticAlgorithm.utils.distance import Distance
        binary = create_problem("b04_onemax", 4)
        continuous = active.create_problem("sphere", 4)
        points = ([0, 0, 0, 0], [1, 0, 0, 0], [1, 1, 0, 0], [1, 1, 1, 1])
        bit_solutions, float_solutions = [], []
        for bits in points:
            b, f = binary.create_solution(), continuous.create_solution()
            b.variables[0], f.variables = list(map(bool, bits)), list(map(float, bits))
            bit_solutions.append(b)
            float_solutions.append(f)
        before = pickle.dumps(bit_solutions)
        self.assertEqual([3, 0], Distance().maxDistanceTab(bit_solutions, 2))
        for count in (1, 2, 3, 4):
            self.assertEqual(Distance().maxDistanceTab(float_solutions, count),
                             Distance().maxDistanceTab(bit_solutions, count))
        self.assertEqual(before, pickle.dumps(bit_solutions))

    def test_all_problems_run_in_jmetal_ga(self):
        # All forty defaults and all thirty 200D adapters exercise initialization, evaluation,
        # selection, mutation, crossover, replacement and termination.
        cases = [(name, None) for name in BENCHMARKS] + [(name, 200) for name in CONTINUOUS_BENCHMARKS]
        for name, dimension in cases:
            with self.subTest(name=name, dimension=dimension):
                problem = create_problem(name, dimension)
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
        for name, dimension in (("r29_composition7", 30), ("r30_composition8", 200), ("b03_nk_k4", 60)):
            with tempfile.TemporaryDirectory(prefix="refined-builder-") as temporary:
                root = Path(temporary)
                config_dir = root / "islands_desync/geneticAlgorithm/algorithm/configurations"
                config_dir.mkdir(parents=True)
                shutil.copyfile(ga_root / "algorithm/configurations/algorithm_configuration.json", config_dir / "algorithm_configuration.json")
                shutil.copyfile(ga_root / "run_algorithm.py", root / "islands_desync/geneticAlgorithm/run_algorithm.py")
                params = RunAlgorithmParams(1, 2, 20, "refined_test", "000001", 1, "ring", "random", "plain")
                env = {"ISLANDS_PROBLEM": name, "ISLANDS_NUMBER_OF_VARIABLES": str(dimension),
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
                    self.assertIn("active_operators", manifest)
                    self.assertIn(f"{name[:4]}{dimension}", str(run))
                    self.assertEqual(dimension, manifest["dimension"])
                    if dimension == 200:
                        self.assertFalse(manifest["official_cec2014_instance"])
                        self.assertEqual("islandsea-cec2014-d200-v1", manifest["instance"])
                    self.assertEqual(name, json.loads((run / "param.json").read_text())["problem"])
                finally:
                    # The legacy logger normally closes these at run end;
                    # this test intentionally stops after the first step.
                    if algorithm is not None:
                        for attribute in ("resultfile", "winnerfile"):
                            getattr(algorithm, attribute).fileSB.close()
                    os.chdir(original_cwd)
