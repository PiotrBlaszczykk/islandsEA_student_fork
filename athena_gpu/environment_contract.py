#!/usr/bin/env python3
"""Inspect the pinned Python environment used by the Athena study runner.

The check intentionally reads distribution metadata without importing the
scientific stack.  This makes failures deterministic and produces a useful
artifact even when a binary extension is broken.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import json
from pathlib import Path
import platform
import sys


ATHENA_PYTHON = (3, 10, 4)

# ``algorithm/requirements.txt`` plus the packages that are required by the
# maintained Ray path and the already validated A100 backend.  These versions
# are the environment recorded in athena-info/ATHENA_CONFIG.md.
ATHENA_EXPECTED_DISTRIBUTIONS = {
    "colorama": "0.4.4",
    "cycler": "0.11.0",
    "fonttools": "4.28.2",
    "jmetalpy": "1.5.5",
    "kiwisolver": "1.3.2",
    "matplotlib": "3.5.0",
    "numpy": "1.21.4",
    "packaging": "21.3",
    "pandas": "1.3.4",
    "patsy": "0.5.2",
    "pika": "1.2.0",
    "pillow": "8.4.0",
    "plotly": "5.4.0",
    "pyparsing": "3.0.6",
    "python-dateutil": "2.8.2",
    "pytz": "2021.3",
    "scipy": "1.7.3",
    "setuptools-scm": "6.3.2",
    "six": "1.16.0",
    "statsmodels": "0.13.1",
    "tenacity": "8.0.1",
    "tomli": "1.2.2",
    "tqdm": "4.62.3",
    "ray": "2.9.3",
    "scikit-learn": "1.1.3",
    "setuptools": "58.1.0",
    "cupy-cuda117": "10.6.0",
    "fastrlock": "0.8.3",
}


def canonical_name(name: str) -> str:
    """Return the PEP 503-style key used for metadata comparisons."""
    return "-".join(part for part in name.strip().lower().replace("_", "-").split("-") if part)


def installed_distributions(distributions=None) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    source = importlib.metadata.distributions() if distributions is None else distributions
    for distribution in source:
        raw_name = distribution.metadata.get("Name") or getattr(distribution, "name", "")
        name = canonical_name(raw_name)
        if name:
            result.setdefault(name, []).append(str(distribution.version))
    return {name: sorted(versions) for name, versions in sorted(result.items())}


def environment_report(*, distributions=None, version_info=None) -> dict:
    version = tuple((version_info or sys.version_info)[:3])
    installed = installed_distributions(distributions)
    expected = dict(ATHENA_EXPECTED_DISTRIBUTIONS)
    missing = sorted(name for name in expected if name not in installed)
    mismatched = {
        name: {"expected": expected[name], "installed": installed[name]}
        for name in sorted(expected)
        if name in installed and installed[name] != [expected[name]]
    }
    cupy_distributions = {
        name: versions
        for name, versions in installed.items()
        if name == "cupy" or name.startswith("cupy-cuda")
    }
    expected_cupy = {"cupy-cuda117": ["10.6.0"]}
    errors = []
    if version != ATHENA_PYTHON:
        errors.append(
            f"Python {'.'.join(map(str, version))} != Athena "
            f"{'.'.join(map(str, ATHENA_PYTHON))}"
        )
    if missing:
        errors.append("missing distributions: " + ", ".join(missing))
    if mismatched:
        errors.append("version mismatches: " + ", ".join(mismatched))
    if cupy_distributions != expected_cupy:
        errors.append(f"CuPy distribution set {cupy_distributions!r} != {expected_cupy!r}")
    return {
        "schema_version": 1,
        "status": "passed" if not errors else "failed",
        "python": {
            "expected": ".".join(map(str, ATHENA_PYTHON)),
            "installed": ".".join(map(str, version)),
            "executable": sys.executable,
            "implementation": platform.python_implementation(),
        },
        "expected_distributions": expected,
        "installed_expected_distributions": {
            name: installed[name] for name in expected if name in installed
        },
        "missing_distributions": missing,
        "version_mismatches": mismatched,
        "cupy_distributions": cupy_distributions,
        "errors": errors,
    }


def _write(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    report = environment_report()
    if args.output:
        _write(args.output.resolve(), report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
