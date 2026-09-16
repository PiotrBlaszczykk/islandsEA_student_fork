import unittest

from athena_gpu.environment_contract import (
    ATHENA_EXPECTED_DISTRIBUTIONS,
    ATHENA_PYTHON,
    canonical_name,
    environment_report,
)


class _Distribution:
    def __init__(self, name, version):
        self.metadata = {"Name": name}
        self.version = version


def _expected_distributions():
    return [
        _Distribution(name, version)
        for name, version in ATHENA_EXPECTED_DISTRIBUTIONS.items()
    ]


class EnvironmentContractTests(unittest.TestCase):
    def test_exact_athena_environment_passes(self):
        report = environment_report(
            distributions=_expected_distributions(),
            version_info=ATHENA_PYTHON,
        )
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["errors"], [])

    def test_python_package_and_mixed_cupy_differences_fail(self):
        distributions = _expected_distributions()
        distributions = [
            item
            for item in distributions
            if canonical_name(item.metadata["Name"]) != "numpy"
        ]
        distributions.extend(
            [
                _Distribution("numpy", "2.3.5"),
                _Distribution("cupy", "10.6.0"),
            ]
        )
        report = environment_report(
            distributions=distributions,
            version_info=(3, 12, 10),
        )
        self.assertEqual(report["status"], "failed")
        self.assertIn("numpy", report["version_mismatches"])
        self.assertEqual(set(report["cupy_distributions"]), {"cupy", "cupy-cuda117"})
        self.assertTrue(any(error.startswith("Python 3.12.10") for error in report["errors"]))

    def test_distribution_names_are_canonicalized(self):
        self.assertEqual(canonical_name("scikit_learn"), "scikit-learn")
        self.assertEqual(canonical_name("Pillow"), "pillow")


if __name__ == "__main__":
    unittest.main()
