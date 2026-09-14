#!/usr/bin/env python3
"""Strict one-A100 readiness test for the first batched IslandsEA benchmark."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import socket
import subprocess
import sys
import time
import traceback


GIB = 1024 ** 3
BATCH_SIZES = (4, 16, 64, 256, 1024, 4096)
VALIDATION_BATCH_SIZE = 32
REPEATS = 5


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _distribution_version(name: str) -> str:
    import importlib.metadata

    return importlib.metadata.version(name)


def _nvidia_smi() -> str:
    result = subprocess.run(
        [
            "nvidia-smi",
            "--query-gpu=index,uuid,name,driver_version,memory.total",
            "--format=csv,noheader",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _cpu_f1_batch(vectors, shift, matrix, weights):
    import numpy as np

    transformed = (vectors - shift) @ matrix.T
    return np.sum(weights * transformed * transformed, axis=1) + 100.0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ray-temp-dir", type=Path, required=True)
    parser.add_argument("--ray-memory-gib", type=int, default=96)
    parser.add_argument("--object-store-gib", type=int, default=8)
    return parser.parse_args()


def _run(args: argparse.Namespace) -> dict:
    import numpy as np
    import ray

    project_dir = args.project_dir.resolve()
    runtime_dir = project_dir / "islands_desync"
    if not (runtime_dir / "islands_desync").is_dir():
        raise RuntimeError(f"Invalid project directory: {project_dir}")
    sys.path.insert(0, str(runtime_dir))

    from islands_desync.geneticAlgorithm.utils.benchmarks_refined import (
        create_evaluator,
    )

    if not os.environ.get("SLURM_JOB_ID"):
        raise RuntimeError("This test must run inside a SLURM allocation")
    if socket.gethostname().split(".")[0].startswith("login"):
        raise RuntimeError("Refusing to run on a login node")
    if not os.environ.get("CUDA_VISIBLE_DEVICES"):
        raise RuntimeError("CUDA_VISIBLE_DEVICES is empty")
    if not str(args.ray_temp_dir).startswith("/tmp/r"):
        raise RuntimeError(f"Ray temp must use a short /tmp/r... path: {args.ray_temp_dir}")

    cpus = int(os.environ.get("SLURM_CPUS_PER_TASK", "0"))
    if cpus != 16:
        raise RuntimeError(f"Expected 16 SLURM CPUs, got {cpus}")
    ray_memory = args.ray_memory_gib * GIB
    object_store_memory = args.object_store_gib * GIB
    if ray_memory + object_store_memory > 104 * GIB:
        raise RuntimeError("Ray memory caps leave less than 21 GiB of the 125 GiB job allocation")

    evaluator = create_evaluator("r01_elliptic", 200)
    shift = np.asarray(evaluator._shifts[0], dtype=np.float64)
    matrix = np.asarray(evaluator._matrices[0], dtype=np.float64)
    weights = 10.0 ** (6.0 * np.arange(200, dtype=np.float64) / 199.0)
    rng = np.random.RandomState(20260914)
    validation_vectors = rng.uniform(-100.0, 100.0, size=(VALIDATION_BATCH_SIZE, 200))

    # The public scalar evaluator remains the correctness oracle. A vectorized
    # NumPy form is checked against it before being used for timing.
    scalar_reference = np.asarray([evaluator(row) for row in validation_vectors])
    cpu_batch_reference = _cpu_f1_batch(validation_vectors, shift, matrix, weights)
    np.testing.assert_allclose(cpu_batch_reference, scalar_reference, rtol=1e-12, atol=1e-6)

    cpu_timings = []
    benchmark_inputs = {}
    for batch_size in BATCH_SIZES:
        host_batch = rng.uniform(-100.0, 100.0, size=(batch_size, 200))
        benchmark_inputs[batch_size] = host_batch
        samples = []
        for _ in range(REPEATS):
            started = time.perf_counter()
            values = _cpu_f1_batch(host_batch, shift, matrix, weights)
            samples.append(time.perf_counter() - started)
        if not np.all(np.isfinite(values)):
            raise FloatingPointError(f"CPU batch {batch_size} produced non-finite values")
        cpu_timings.append(
            {
                "batch_size": batch_size,
                "seconds": samples,
                "median_seconds": float(np.median(samples)),
                "evaluations_per_second": float(batch_size / np.median(samples)),
            }
        )

    ray.init(
        num_cpus=cpus,
        num_gpus=1,
        include_dashboard=False,
        _temp_dir=str(args.ray_temp_dir),
        _memory=ray_memory,
        object_store_memory=object_store_memory,
    )

    @ray.remote(num_cpus=1, num_gpus=1, max_restarts=0, max_task_retries=0)
    class F1GpuActor:
        def __init__(self, shift_array, matrix_array, weight_array):
            import cupy as cp

            self.cp = cp
            self.shift = cp.asarray(shift_array, dtype=cp.float64)
            self.matrix_t = cp.asarray(matrix_array.T, dtype=cp.float64)
            self.weights = cp.asarray(weight_array, dtype=cp.float64)
            # Force context creation and CuPy kernel compilation before timing.
            warm = cp.zeros((4, self.shift.size), dtype=cp.float64)
            self._evaluate_device(warm)
            cp.cuda.Stream.null.synchronize()

        def _evaluate_device(self, vectors):
            transformed = (vectors - self.shift) @ self.matrix_t
            return self.cp.sum(self.weights * transformed * transformed, axis=1) + 100.0

        def evaluate(self, host_vectors):
            cp = self.cp
            total_started = time.perf_counter()
            device_vectors = cp.asarray(host_vectors, dtype=cp.float64)
            h2d_finished = time.perf_counter()
            event_start = cp.cuda.Event()
            event_end = cp.cuda.Event()
            event_start.record()
            device_values = self._evaluate_device(device_vectors)
            event_end.record()
            event_end.synchronize()
            kernel_seconds = float(cp.cuda.get_elapsed_time(event_start, event_end) / 1000.0)
            host_values = cp.asnumpy(device_values)
            total_finished = time.perf_counter()
            return {
                "values": host_values,
                "h2d_submit_seconds": h2d_finished - total_started,
                "kernel_seconds": kernel_seconds,
                "actor_end_to_end_seconds": total_finished - total_started,
            }

        def environment(self):
            cp = self.cp
            properties = cp.cuda.runtime.getDeviceProperties(0)
            name = properties.get("name", properties.get(b"name", "unknown"))
            if isinstance(name, bytes):
                name = name.decode("utf-8", errors="replace")
            free_memory, total_memory = cp.cuda.runtime.memGetInfo()
            return {
                "host": socket.gethostname(),
                "pid": os.getpid(),
                "CUDA_VISIBLE_DEVICES": os.environ.get("CUDA_VISIBLE_DEVICES"),
                "ray_gpu_ids": ray.get_gpu_ids(),
                "cupy_version": cp.__version__,
                "cuda_runtime_version": int(cp.cuda.runtime.runtimeGetVersion()),
                "cuda_driver_version": int(cp.cuda.runtime.driverGetVersion()),
                "device_name": str(name),
                "device_free_memory_bytes": int(free_memory),
                "device_total_memory_bytes": int(total_memory),
            }

    actor = F1GpuActor.remote(shift, matrix, weights)
    actor_environment = ray.get(actor.environment.remote(), timeout=120)
    if actor_environment["ray_gpu_ids"] != [0]:
        raise RuntimeError(f"Unexpected Ray GPU ids: {actor_environment['ray_gpu_ids']}")

    validation_result = ray.get(actor.evaluate.remote(validation_vectors), timeout=120)
    gpu_validation = np.asarray(validation_result["values"], dtype=np.float64)
    np.testing.assert_allclose(gpu_validation, scalar_reference, rtol=1e-12, atol=1e-6)
    absolute_error = np.abs(gpu_validation - scalar_reference)
    relative_error = absolute_error / np.maximum(np.abs(scalar_reference), 1.0)

    gpu_timings = []
    for batch_size in BATCH_SIZES:
        host_batch = benchmark_inputs[batch_size]
        # First call for each shape is excluded to avoid counting shape-specific
        # allocator/dispatch warm-up as steady-state throughput.
        ray.get(actor.evaluate.remote(host_batch), timeout=120)
        samples = []
        for _ in range(REPEATS):
            roundtrip_started = time.perf_counter()
            measurement = ray.get(actor.evaluate.remote(host_batch), timeout=120)
            roundtrip_seconds = time.perf_counter() - roundtrip_started
            samples.append(
                {
                    "ray_roundtrip_seconds": roundtrip_seconds,
                    "actor_end_to_end_seconds": measurement["actor_end_to_end_seconds"],
                    "h2d_submit_seconds": measurement["h2d_submit_seconds"],
                    "kernel_seconds": measurement["kernel_seconds"],
                }
            )
        roundtrips = np.asarray([item["ray_roundtrip_seconds"] for item in samples])
        kernels = np.asarray([item["kernel_seconds"] for item in samples])
        gpu_timings.append(
            {
                "batch_size": batch_size,
                "samples": samples,
                "median_ray_roundtrip_seconds": float(np.median(roundtrips)),
                "median_kernel_seconds": float(np.median(kernels)),
                "ray_roundtrip_evaluations_per_second": float(batch_size / np.median(roundtrips)),
                "kernel_evaluations_per_second": float(batch_size / np.median(kernels)),
            }
        )

    cluster_resources = ray.cluster_resources()
    available_resources = ray.available_resources()
    actual_ray_memory = float(cluster_resources.get("memory", -1.0))
    actual_object_store = float(cluster_resources.get("object_store_memory", -1.0))
    memory_tolerance = 16 * 1024 ** 2
    if abs(actual_ray_memory - ray_memory) > memory_tolerance:
        raise RuntimeError(
            f"Ray memory resource is not capped: expected {ray_memory}, got {actual_ray_memory}"
        )
    if abs(actual_object_store - object_store_memory) > memory_tolerance:
        raise RuntimeError(
            "Ray object store is not capped: "
            f"expected {object_store_memory}, got {actual_object_store}"
        )
    if float(cluster_resources.get("CPU", -1.0)) != 16.0:
        raise RuntimeError(f"Ray CPU resource mismatch: {cluster_resources}")
    if float(cluster_resources.get("GPU", -1.0)) != 1.0:
        raise RuntimeError(f"Ray GPU resource mismatch: {cluster_resources}")

    ray.shutdown()

    return {
        "schema_version": 1,
        "status": "ok",
        "created_timestamp_unix": time.time(),
        "purpose": "Athena one-A100 readiness; not an IslandsEA experiment",
        "slurm": {
            "job_id": os.environ["SLURM_JOB_ID"],
            "account": os.environ.get("SLURM_JOB_ACCOUNT"),
            "partition": os.environ.get("SLURM_JOB_PARTITION"),
            "cpus_per_task": cpus,
            "job_gpus": os.environ.get("SLURM_JOB_GPUS"),
            "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
        },
        "host": {
            "hostname": socket.gethostname(),
            "platform": platform.platform(),
            "python": sys.version,
            "executable": sys.executable,
            "nvidia_smi": _nvidia_smi(),
        },
        "software": {
            "ray": ray.__version__,
            "numpy": np.__version__,
            "cupy_distribution": "cupy-cuda117",
            "cupy_distribution_version": _distribution_version("cupy-cuda117"),
            "cuda_module": "CUDA/11.7.0",
        },
        "benchmark": {
            "name": "r01_elliptic",
            "dimension": 200,
            "dtype": "float64",
            "data_sha256": evaluator.metadata()["data_sha256"],
            "implementation_sha256": evaluator.metadata().get("implementation_sha256"),
            "validation_batch_size": VALIDATION_BATCH_SIZE,
            "rtol": 1e-12,
            "atol": 1e-6,
            "max_absolute_error": float(np.max(absolute_error)),
            "max_relative_error": float(np.max(relative_error)),
        },
        "ray": {
            "requested_memory_bytes": ray_memory,
            "requested_object_store_memory_bytes": object_store_memory,
            "cluster_resources": cluster_resources,
            "available_resources_after_actor": available_resources,
            "temp_dir": str(args.ray_temp_dir),
            "actor": actor_environment,
        },
        "timings": {
            "repeats": REPEATS,
            "cpu_vectorized": cpu_timings,
            "gpu_via_ray": gpu_timings,
        },
    }


def main() -> int:
    args = _parse_args()
    try:
        payload = _run(args)
    except Exception as error:
        payload = {
            "schema_version": 1,
            "status": "failed",
            "created_timestamp_unix": time.time(),
            "error_type": type(error).__name__,
            "error": str(error),
            "traceback": traceback.format_exc(),
            "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
            "host": socket.gethostname(),
        }
        _atomic_json(args.output, payload)
        print(f"ATHENA_GPU_READINESS_FAILED={type(error).__name__}", file=sys.stderr)
        return 1

    _atomic_json(args.output, payload)
    print("ATHENA_CUPY_KERNEL_OK=1")
    print("ATHENA_R01_CPU_GPU_MATCH=1")
    print("ATHENA_RAY_MEMORY_LIMITS_OK=1")
    print("ATHENA_RAY_GPU_ACTOR_OK=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
