"""Guard the short BA diagnostic against drifting into a study campaign."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_ba_smoke as smoke


class BaSmokeContractTests(unittest.TestCase):
    def setUp(self):
        self.metadata = {
            "status": "complete", "run_id": "test-run",
            "scientific_configuration": {
                "study": "diagnostic", "benchmark": {"name": "r01_elliptic"},
                "dimension": 200, "islands": 144, "evaluations_per_island": 128,
                "population": 16, "offspring": 4, "repeat": 1,
                "migration": {
                    "group_size": 5, "interval": 5,
                    "interval_unit": "evaluation-count difference",
                    "selection": "best", "acceptance": "plain",
                },
                "topology": {"name": "ba", "parameters": smoke.campaign.BA_PARAMETERS,
                             "adjacency_sha256": smoke.campaign.BA_ADJACENCY_SHA256},
                "seed": {"requested_base": 20260912, "repeat_base": 20260912},
                "metrics": {"profile": "research-v1-full-buffered",
                            "effect_horizon_steps": 25,
                            "delivery_ack_timeout_seconds": 300.0},
            },
            "resources": {
                "required_ray_cpus": 289, "required_slurm_cpus": 290,
                "slurm": {"SLURM_JOB_ID": "123", "SLURM_JOB_NUM_NODES": "7",
                          "SLURM_JOB_ACCOUNT": "plglscclass26-cpu",
                          "SLURM_JOB_PARTITION": "plgrid",
                          "ISLANDS_ALLOCATED_CPUS_PER_NODE": "48"},
            },
            "provenance": {"git_dirty": False},
        }

    def test_approved_ba_diagnostic_contract(self):
        smoke.campaign.validate_study_graph_source()
        smoke.validate_configuration(self.metadata, "123")

    def test_full_run_is_not_misidentified_as_smoke(self):
        changed = copy.deepcopy(self.metadata)
        changed["scientific_configuration"]["study"] = "approved-144"
        changed["scientific_configuration"]["evaluations_per_island"] = 8000
        with self.assertRaisesRegex(ValueError, "diagnostic"):
            smoke.validate_configuration(changed, "123")

    def test_wrong_graph_identity_is_rejected(self):
        changed = copy.deepcopy(self.metadata)
        changed["scientific_configuration"]["topology"]["adjacency_sha256"] = "wrong"
        with self.assertRaisesRegex(ValueError, "BA adjacency"):
            smoke.validate_configuration(changed, "123")


if __name__ == "__main__":
    unittest.main()
