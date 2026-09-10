from __future__ import annotations

import argparse
import importlib.metadata
import os
from pathlib import Path
import platform
import socket
import sys


def package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "NOT_INSTALLED"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Minimalny smoke test venv + Ray na Aresie.")
    parser.add_argument("--expected-venv", required=True)
    parser.add_argument("--ray-temp-dir", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    expected_venv = Path(args.expected_venv).resolve()
    active_venv = Path(sys.prefix).resolve()

    print("=== ARES ENVIRONMENT ===")
    print("host:", socket.gethostname())
    print("platform:", platform.platform())
    print("python:", sys.version.replace("\n", " "))
    print("executable:", sys.executable)
    print("sys.prefix:", active_venv)
    print("SLURM_JOB_ID:", os.environ.get("SLURM_JOB_ID", "brak"))
    print("SLURM_CPUS_PER_TASK:", os.environ.get("SLURM_CPUS_PER_TASK", "brak"))

    if active_venv != expected_venv:
        print(f"ERROR: aktywny venv to {active_venv}, oczekiwano {expected_venv}", file=sys.stderr)
        return 2

    print("=== PROJECT PACKAGES ===")
    for package in ("ray", "jmetalpy", "numpy", "scikit-learn", "setuptools"):
        print(f"{package}: {package_version(package)}")

    missing = [
        package
        for package in ("ray", "jmetalpy", "numpy", "scikit-learn")
        if package_version(package) == "NOT_INSTALLED"
    ]
    if missing:
        print(f"ERROR: brak pakietow: {', '.join(missing)}", file=sys.stderr)
        return 3

    import ray

    ray_temp_dir = Path(args.ray_temp_dir)
    ray_temp_dir.mkdir(parents=True, exist_ok=True)
    requested_cpus = max(1, int(os.environ.get("SLURM_CPUS_PER_TASK", "1")))

    print("=== RAY ===")
    print("ray temp dir:", ray_temp_dir)
    print("requested CPUs:", requested_cpus)

    ray.init(
        num_cpus=requested_cpus,
        include_dashboard=False,
        _temp_dir=str(ray_temp_dir),
        logging_level="ERROR",
    )

    try:
        @ray.remote
        def hello_from_ray() -> dict[str, str | int]:
            return {
                "message": "hello from Ray on Ares",
                "host": socket.gethostname(),
                "pid": os.getpid(),
                "python": sys.executable,
            }

        result = ray.get(hello_from_ray.remote())
        print("Ray result:", result)
        print("Ray resources:", ray.available_resources())

        if result["message"] != "hello from Ray on Ares":
            print("ERROR: niepoprawny wynik zadania Ray", file=sys.stderr)
            return 4
    finally:
        ray.shutdown()

    print("SMOKE_TEST_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

