"""List definitions, export instance metadata, or run the sanity checks."""
import argparse
import importlib.metadata
import json
from pathlib import Path
import platform
import sys
import unittest

from . import BENCHMARKS, CONTINUOUS_BENCHMARKS, SUITE_VERSION, create_evaluator
from .discrete import DEFAULT_INSTANCE_SEED
from .provenance import implementation_sha256


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument("--list", action="store_true")
    operation.add_argument("--manifest", choices=BENCHMARKS)
    operation.add_argument("--validate", action="store_true")
    parser.add_argument("--dimension", type=int)
    parser.add_argument("--instance-seed", type=int, default=DEFAULT_INSTANCE_SEED)
    parser.add_argument("--core-only", action="store_true", help="Skip jMetal/active builder tests; do not interpret as full integration validation")
    parser.add_argument("--output", type=Path, help="Manifest or validation report JSON")
    args = parser.parse_args()
    if args.list:
        for name in BENCHMARKS:
            print(name)
        return 0
    if args.manifest:
        result = create_evaluator(args.manifest, args.dimension, instance_seed=args.instance_seed).metadata()
        result.update({"name": args.manifest, "suite_version": SUITE_VERSION, "implementation_sha256": implementation_sha256()})
        success = True
    else:
        modules = ["test_cec2014", "test_discrete"]
        if not args.core_only:
            modules.append("test_integration")
        suite = unittest.defaultTestLoader.loadTestsFromNames([f"{__package__}.tests.{m}" for m in modules])
        run = unittest.TextTestRunner(verbosity=2).run(suite)
        success = run.wasSuccessful() and not run.skipped
        versions = {}
        for package in ("numpy", "jmetalpy", "ray", "scipy", "scikit-learn"):
            try:
                versions[package] = importlib.metadata.version(package)
            except importlib.metadata.PackageNotFoundError:
                versions[package] = None
        result = {"success": success, "tests_run": run.testsRun, "failures": len(run.failures),
                  "errors": len(run.errors), "skipped": len(run.skipped), "core_only": args.core_only,
                  "python": platform.python_version(), "platform": platform.platform(), "versions": versions,
                  "suite_version": SUITE_VERSION, "implementation_sha256": implementation_sha256(),
                  "cec_reference_cases": 1776, "continuous_count": 30, "discrete_count": 10,
                  "ares_slurm_validated": False}
    payload = json.dumps(result, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
