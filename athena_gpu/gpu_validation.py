#!/usr/bin/env python3
"""Bounded validation of all 40 canonical batch functions in a real GPU actor.

No island execution, GA, batcher or campaign submission. A passing result is
evidence about this backend/commit on this device, not the future scheduler.
"""
import argparse
import importlib.metadata
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time
import traceback

from gpu_readiness import _atomic_json, _nvidia_smi

GIB = 1024 ** 3
SIZES = (200, 400, 800, 1200, 1600, 2400, 3200)


def _check_commit(project_dir):
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=project_dir, text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=all"], cwd=project_dir, text=True)
    if not os.environ.get("ATHENA_EXPECTED_COMMIT") or commit != os.environ["ATHENA_EXPECTED_COMMIT"] or dirty:
        raise RuntimeError("Validation requires the pinned clean checkout throughout the job")
    return commit


def run(args):
    if not os.environ.get("SLURM_JOB_ID") or socket.gethostname().split(".")[0].startswith("login"):
        raise RuntimeError("Run only in a SLURM GPU compute allocation")
    if int(os.environ.get("SLURM_CPUS_PER_TASK", "0")) != 16 or not os.environ.get("CUDA_VISIBLE_DEVICES"):
        raise RuntimeError("Expected 16 CPUs and one allocated GPU")
    if str(args.ray_temp_dir) != "/tmp/r" + os.environ["SLURM_JOB_ID"] or not re.fullmatch(r"/tmp/r[0-9]+", str(args.ray_temp_dir)):
        raise RuntimeError("Invalid job-specific short Ray directory")
    if args.ray_memory_gib != 96 or args.object_store_gib != 8:
        raise RuntimeError("Use the validated Athena 96/8 GiB memory profile")
    commit = _check_commit(args.project_dir)
    sys.path.insert(0, str(args.project_dir.resolve() / "islands_desync"))
    import numpy as np
    import ray
    from islands_desync.geneticAlgorithm.utils.benchmarks_refined.batch import NumpyBatchBackend
    from islands_desync.geneticAlgorithm.utils.benchmarks_refined.batch_validation import tolerances
    expected_versions = {"ray": "2.9.3", "numpy": "1.21.4", "scipy": "1.7.3",
                         "jmetalpy": "1.5.5", "cupy-cuda117": "10.6.0"}
    versions = {name: importlib.metadata.version(name) for name in expected_versions}
    if sys.version_info[:2] != (3, 10) or versions != expected_versions:
        raise RuntimeError(f"Athena requires the pinned Python 3.10 stack: {versions}")

    ray.init(address="local", num_cpus=15, num_gpus=1, include_dashboard=False, _temp_dir=str(args.ray_temp_dir),
             _memory=96*GIB, object_store_memory=8*GIB)
    try:
        resources = ray.cluster_resources()
        if resources.get("GPU") != 1 or resources.get("CPU") != 15:
            raise RuntimeError(f"Unexpected Ray resources: {resources}")
        for key, expected in (("memory", 96*GIB), ("object_store_memory", 8*GIB)):
            if abs(resources.get(key, 0)-expected) > 16*1024**2:
                raise RuntimeError(f"Ray did not respect {key} limit")

        @ray.remote(num_cpus=1, num_gpus=1, max_restarts=0, max_task_retries=0)
        class ValidationActor:
            def __init__(self):
                import cupy as cp
                from islands_desync.geneticAlgorithm.utils.benchmarks_refined.batch import CupyBatchBackend
                from islands_desync.geneticAlgorithm.utils.benchmarks_refined.batch_validation import validate_backend
                if cp.__version__ != "10.6.0" or cp.cuda.runtime.runtimeGetVersion() != 11070:
                    raise RuntimeError("Expected pinned CuPy 10.6.0 / CUDA runtime 11.7")
                if len(ray.get_gpu_ids()) != 1 or cp.cuda.runtime.getDeviceCount() != 1:
                    raise RuntimeError("GPU actor must see exactly its allocated GPU")
                self.cp, self.validate = cp, validate_backend
                self.backend = CupyBatchBackend()

            def validate_all(self):
                report = self.validate(self.backend)
                if report["benchmark_count"] != 40 or report["instance_count"] != 170:
                    raise AssertionError("Incomplete validation matrix")
                for item in report["instances"]:
                    profile = item["large_batch_profile"]
                    if profile.get("h2d_count") != 1 or profile.get("d2h_count") != 1 or profile.get("kernel_device_seconds", 0) <= 0:
                        raise AssertionError("No measured GPU evaluation in validation case")
                return report

            def evaluate(self, name, x):
                started = time.perf_counter()
                result = self.backend.evaluate_batch(name, x)
                return result, dict(self.backend.last_profile, actor_seconds=time.perf_counter()-started)

            def environment(self):
                cp = self.cp
                properties = cp.cuda.runtime.getDeviceProperties(cp.cuda.Device().id)
                name = properties.get("name", properties.get(b"name", "unknown"))
                if isinstance(name, bytes):
                    name = name.decode()
                if "A100" not in str(name):
                    raise RuntimeError(f"Expected A100, got {name}")
                free, total = cp.cuda.runtime.memGetInfo()
                return {"device_name": str(name), "ray_gpu_ids": ray.get_gpu_ids(),
                        "cupy": cp.__version__, "runtime": cp.cuda.runtime.runtimeGetVersion(),
                        "driver": cp.cuda.runtime.driverGetVersion(), "hostname": socket.gethostname(),
                        "pid": os.getpid(), "CUDA_VISIBLE_DEVICES": os.environ.get("CUDA_VISIBLE_DEVICES"),
                        "free_device_bytes": free, "total_device_bytes": total,
                        "pool_used_bytes": cp.get_default_memory_pool().used_bytes(),
                        "pool_reserved_bytes": cp.get_default_memory_pool().total_bytes()}

        actor = ValidationActor.remote()
        environment = ray.get(actor.environment.remote(), timeout=120)
        # Explicit cap for this single validation task; no retries/resubmits.
        matrix = ray.get(actor.validate_all.remote(), timeout=600)
        cpu = NumpyBatchBackend()
        rng = np.random.RandomState(20260914)
        timings = []
        # Representatives include a simple, trigonometric, hybrid, composed
        # hybrid, integer-reduction and table-lookup objective.
        for name in ("r01_elliptic", "r06_weierstrass", "r22_hybrid6", "r30_composition8", "b01_labs_binary", "b03_nk_k4"):
            for size in SIZES:
                x = rng.uniform(-100, 100, (size, 200)) if name.startswith("r") else rng.randint(0, 2, (size, 200))
                expected = cpu.evaluate_batch(name, x)
                cpu_samples = []
                for _ in range(3):
                    started = time.perf_counter()
                    cpu.evaluate_batch(name, x)
                    cpu_samples.append(time.perf_counter()-started)
                ray.get(actor.evaluate.remote(name, x), timeout=60)  # shape warmup
                samples = []
                for _ in range(3):
                    started = time.perf_counter()
                    values, profile = ray.get(actor.evaluate.remote(name, x), timeout=60)
                    profile["ray_roundtrip_seconds"] = time.perf_counter()-started
                    np.testing.assert_allclose(values, expected, rtol=tolerances(name)[0], atol=tolerances(name)[1])
                    samples.append(profile)
                cpu_median = float(np.median(cpu_samples))
                gpu_median = float(np.median([s["ray_roundtrip_seconds"] for s in samples]))
                timings.append({"name": name, "dimension": 200, "batch_size": size, "samples": samples,
                                "cpu_batch_seconds": cpu_samples, "cpu_median_seconds": cpu_median,
                                "gpu_ray_median_seconds": gpu_median, "cpu_evaluations_per_second": size/cpu_median,
                                "gpu_ray_evaluations_per_second": size/gpu_median,
                                "gpu_vs_cpu_speedup": cpu_median/gpu_median})
        environment_after = ray.get(actor.environment.remote(), timeout=30)
        if _check_commit(args.project_dir) != commit:
            raise RuntimeError("Checkout changed during validation")
        return {"schema_version": 1, "status": "passed", "purpose": "40-function backend validation, no IslandsEA run",
                "created_unix": time.time(), "git_commit": commit,
                "git_dirty": False, "python": sys.version,
                "slurm": {key: os.environ.get(key) for key in ("SLURM_JOB_ID", "SLURM_JOB_ACCOUNT", "SLURM_JOB_PARTITION", "SLURM_CPUS_PER_TASK", "SLURM_JOB_GPUS")},
                "versions": versions,
                "nvidia_smi": _nvidia_smi(), "ray_resources": resources,
                "ray_temp": str(args.ray_temp_dir), "driver_cpu_reserved": 1,
                "device_before": environment, "device_after": environment_after,
                "validation": matrix, "timings": timings,
                "timing_contract": "Warm CPU batch includes validation; GPU roundtrip includes Ray/transfers; D2H wall time includes pending compute wait",
                "tolerances_policy": "CEC existing C-oracle 1e-10/1e-8; LABS/NK 2e-14/2e-14; other binary exact"}
    finally:
        ray.shutdown()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ray-temp-dir", type=Path, required=True)
    parser.add_argument("--ray-memory-gib", type=int, default=96)
    parser.add_argument("--object-store-gib", type=int, default=8)
    args = parser.parse_args()
    try:
        result = run(args)
        _atomic_json(args.output, result)
        print("ATHENA_40_CPU_GPU_MATCH=1")
        print("ATHENA_40_GPU_VALIDATION_OK=1")
        return 0
    except Exception as error:
        _atomic_json(args.output, {"status": "failed", "error": repr(error), "traceback": traceback.format_exc(),
                                   "slurm_job_id": os.environ.get("SLURM_JOB_ID")})
        print("ATHENA_40_GPU_VALIDATION_FAILED=1", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
