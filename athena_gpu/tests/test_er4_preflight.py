"""Actual GPU-runner preflight of the frozen ER graph; no Ray/GPU allocation."""
import os
import unittest
from unittest.mock import patch

from athena_gpu import run_study


class ER4GPUPreflightTests(unittest.TestCase):
    def test_er4_is_accepted_with_same_cpu_graph_and_gpu_resource_plan(self):
        args = run_study.parser().parse_args([
            "--problem", "r01_elliptic", "--dimension", "200", "--topology", "er4", "--dry-run",
        ])
        with patch.dict(os.environ, run_study.common.environment(args)):
            checked = run_study._validate_scientific_contract(args)
        self.assertEqual(144, len(checked["adjacency"]))
        self.assertEqual(checked["adjacency"], checked["topology_class"](144).create())
        params = run_study.common.graph_parameters("er4")
        self.assertEqual(0.0347, params["probab"])
        self.assertEqual(144, params["provenance"]["graph_statistics"]["largest_component_size"])
        self.assertEqual(15, checked["plan"]["resources"]["actor_cpus"])


if __name__ == "__main__":
    unittest.main()
