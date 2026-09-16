"""Single-owner CuPy backend actor for Athena study runs."""
from __future__ import annotations


def make_actor_class():
    import ray

    @ray.remote(
        num_cpus=1,
        num_gpus=1,
        max_restarts=0,
        max_task_retries=0,
    )
    class GpuEvaluator:
        def __init__(self, *, max_batch_rows: int):
            import os
            import socket

            import cupy as cp

            from islands_desync.geneticAlgorithm.utils.benchmarks_refined.batch import (
                CupyBatchBackend,
            )

            if len(ray.get_gpu_ids()) != 1:
                raise RuntimeError("GpuEvaluator must own exactly one Ray GPU")
            if cp.cuda.runtime.getDeviceCount() != 1:
                raise RuntimeError("GpuEvaluator must see exactly one CUDA device")
            if cp.__version__ != "10.6.0" or cp.cuda.runtime.runtimeGetVersion() != 11070:
                raise RuntimeError("expected pinned CuPy 10.6.0 and CUDA runtime 11.7")
            properties = cp.cuda.runtime.getDeviceProperties(cp.cuda.Device().id)
            name = properties.get("name", properties.get(b"name", "unknown"))
            if isinstance(name, bytes):
                name = name.decode()
            if "A100" not in str(name):
                raise RuntimeError(f"expected an A100, got {name}")
            self.cp = cp
            self.backend = CupyBatchBackend(max_batch_size=max_batch_rows)
            self.calls = 0
            self.rows = 0
            self.hostname = socket.gethostname()
            self.pid = os.getpid()
            self.device_name = str(name)

        def evaluate(self, problem_id, vectors, *, instance_seed):
            values = self.backend.evaluate_batch(
                problem_id,
                vectors,
                instance_seed=instance_seed,
            )
            profile = dict(self.backend.last_profile)
            if vectors.shape[0]:
                if profile.get("h2d_count") != 1 or profile.get("d2h_count") != 1:
                    raise RuntimeError("GPU batch did not perform exactly one H2D and D2H")
                if profile.get("kernel_device_seconds", 0.0) <= 0:
                    raise RuntimeError("GPU batch has no measured kernel execution")
            self.calls += 1
            self.rows += int(vectors.shape[0])
            return {"values": values, "profile": profile}

        def environment(self):
            cp = self.cp
            free, total = cp.cuda.runtime.memGetInfo()
            properties = cp.cuda.runtime.getDeviceProperties(cp.cuda.Device().id)
            return {
                "schema_version": 1,
                "backend": self.backend.backend_name,
                "device_name": self.device_name,
                "ray_gpu_ids": ray.get_gpu_ids(),
                "cupy": cp.__version__,
                "cuda_runtime": cp.cuda.runtime.runtimeGetVersion(),
                "cuda_driver": cp.cuda.runtime.driverGetVersion(),
                "hostname": self.hostname,
                "pid": self.pid,
                "free_device_bytes": int(free),
                "total_device_bytes": int(total),
                "multiprocessor_count": int(
                    properties.get(
                        "multiProcessorCount",
                        properties.get(b"multiProcessorCount", 0),
                    )
                ),
                "calls": self.calls,
                "rows": self.rows,
            }

    return GpuEvaluator
