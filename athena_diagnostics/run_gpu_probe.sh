#!/usr/bin/env bash

# Minimal compute-node probe. Resource selection is supplied by
# collect_athena_info.sh so this file contains no stale cluster defaults.
set -uo pipefail
: "${SLURM_JOB_ID:?Submit through athena_diagnostics/collect_athena_info.sh}"
: "${ATHENA_DIAGNOSTICS_REPORT:?Missing shared diagnostics report path}"

PROJECT_DIR="${ATHENA_PROJECT_DIR:-${HOME}/islandsEA_student_fork}"
VENV_DIR="${ISLANDS_VENV_DIR:-${HOME}/venvs/islands-ray}"
PYTHON_MODULE="${ATHENA_PYTHON_MODULE:-Python/3.10.4}"
PROBE_TMP="/tmp/r${SLURM_JOB_ID}"
if [[ ! "$PROBE_TMP" =~ ^/tmp/r[0-9]+$ ]]; then
    echo "ERROR: refusing unsafe probe tmp path: $PROBE_TMP" >&2
    exit 2
fi
mkdir -p "$PROBE_TMP"
trap 'rm -rf -- "$PROBE_TMP"' EXIT

# The report is deliberately small and lives in HOME/artifacts for easy scp.
# The normal SLURM stdout/stderr remains a separate file under SCRATCH.
exec >>"$ATHENA_DIAGNOSTICS_REPORT" 2>&1

if [[ -x "$VENV_DIR/bin/python" ]]; then
    module load "$PYTHON_MODULE"
fi

section() {
    printf '\n===== %s =====\n' "$1"
}

run_command() {
    local title="$1"
    shift
    section "$title"
    printf 'COMMAND:'
    printf ' %q' "$@"
    printf '\n'
    "$@" 2>&1
    local status=$?
    if [[ "$status" -ne 0 ]]; then
        printf 'COMMAND_FAILED exit=%s\n' "$status"
    fi
    return 0
}

section "GPU COMPUTE-NODE PROBE"
echo "started_at=$(date --iso-8601=seconds)"
echo "job_id=$SLURM_JOB_ID"
echo "host=$(hostname -f)"
echo "project_dir=$PROJECT_DIR"
echo "venv_dir=$VENV_DIR"
echo "python_module=$PYTHON_MODULE"
echo "probe_tmp=$PROBE_TMP"

section "SLURM AND GPU ENVIRONMENT"
env | grep -E '^(SLURM|CUDA|NVIDIA|ROCR|GPU|RAY|UCX|NCCL|OMP|MKL|OPENBLAS|TMPDIR)=' \
    | sort || true

run_command "SLURM JOB DESCRIPTION" scontrol show job "$SLURM_JOB_ID"
run_command "SLURM NODE DESCRIPTION" scontrol show node "$(hostname -s)"
run_command "PROCESS AFFINITY" taskset -pc "$$"
run_command "CGROUP" bash -c 'cat /proc/self/cgroup'
run_command "CPU DESCRIPTION" lscpu
run_command "NUMA DESCRIPTION" numactl --hardware
run_command "MEMORY" free -h
run_command "FILESYSTEMS" df -h "$HOME" "${SCRATCH:-$HOME}" /tmp /dev/shm
run_command "FILESYSTEM INODES" df -i "$HOME" "${SCRATCH:-$HOME}" /tmp

run_command "NVIDIA-SMI VERSION" nvidia-smi
run_command "GPU LIST" nvidia-smi -L
run_command "GPU PROPERTIES" nvidia-smi \
    --query-gpu=index,uuid,name,pci.bus_id,driver_version,memory.total,compute_cap,persistence_mode,power.limit \
    --format=csv
run_command "GPU TOPOLOGY" nvidia-smi topo -m
run_command "GPU NVLINK STATUS" nvidia-smi nvlink --status
run_command "GPU DEVICE FILES" bash -c 'ls -l /dev/nvidia* 2>&1 || true'
run_command "PCI NVIDIA DEVICES" bash -c 'lspci -nn | grep -i nvidia || true'

section "MODULES ON COMPUTE NODE"
module list 2>&1 || true
module -t avail 2>&1 \
    | grep -Ei '(^|/)(python|cuda|cudnn|nccl|gcc|nvhpc|openmpi|ucx|ray|pytorch|tensorflow|cupy)' \
    | head -n 500 || true

run_command "CUDA COMPILER" bash -c 'command -v nvcc && nvcc --version'
run_command "CUDA/NVIDIA LIBRARIES" bash -c \
    "ldconfig -p 2>/dev/null | grep -Ei 'cuda|nvidia|nccl' | head -n 200 || true"
run_command "NETWORK ADDRESSES" bash -c 'hostname -I; ip -br address 2>&1 || true'
run_command "INFINIBAND DEVICES" bash -c \
    'if command -v ibv_devinfo >/dev/null 2>&1; then ibv_devinfo; elif command -v ibstat >/dev/null 2>&1; then ibstat; else echo INFINIBAND_TOOLS_NOT_FOUND; fi'

section "PROJECT VENV ON GPU NODE"
if [[ -x "$VENV_DIR/bin/python" ]]; then
    "$VENV_DIR/bin/python" - <<'PY'
import importlib.metadata
import os
import platform
import socket
import sys

print("host:", socket.gethostname())
print("python:", sys.version.replace("\n", " "))
print("executable:", sys.executable)
print("prefix:", sys.prefix)
print("platform:", platform.platform())
print("cpu_count:", os.cpu_count())
print("CUDA_VISIBLE_DEVICES:", os.environ.get("CUDA_VISIBLE_DEVICES"))
for package in (
    "ray", "jmetalpy", "numpy", "scipy", "scikit-learn", "pandas",
    "matplotlib", "setuptools", "wheel", "packaging", "torch", "cupy",
    "tensorflow", "jax", "jaxlib", "numba",
):
    try:
        version = importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        version = "NOT_INSTALLED"
    print(f"{package}: {version}")
PY
    run_command "PIP CHECK ON GPU NODE" "$VENV_DIR/bin/python" -m pip check

    section "PYTHON GPU FRAMEWORK VISIBILITY"
    PROBE_TMP="$PROBE_TMP" "$VENV_DIR/bin/python" - <<'PY'
import importlib.util
import json
import os
import traceback

result = {}
if importlib.util.find_spec("torch"):
    try:
        import torch
        result["torch"] = {
            "version": torch.__version__,
            "cuda_build": torch.version.cuda,
            "cuda_available": torch.cuda.is_available(),
            "device_count": torch.cuda.device_count(),
            "devices": [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())],
        }
        if torch.cuda.is_available():
            value = (torch.ones(32, device="cuda") * 2).sum().item()
            result["torch"]["gpu_smoke_sum"] = value
    except Exception:
        result["torch_error"] = traceback.format_exc()
if importlib.util.find_spec("cupy"):
    try:
        import cupy
        result["cupy"] = {
            "version": cupy.__version__,
            "device_count": cupy.cuda.runtime.getDeviceCount(),
            "gpu_smoke_sum": float(cupy.sum(cupy.ones(32) * 2).get()),
        }
    except Exception:
        result["cupy_error"] = traceback.format_exc()
if importlib.util.find_spec("jax"):
    try:
        import jax
        result["jax"] = {"version": jax.__version__, "devices": [str(d) for d in jax.devices()]}
    except Exception:
        result["jax_error"] = traceback.format_exc()
print(json.dumps(result or {"gpu_python_frameworks": "NOT_INSTALLED"}, indent=2, sort_keys=True))
PY

    section "RAY GPU RESOURCE PROBE"
    if PROBE_TMP="$PROBE_TMP" "$VENV_DIR/bin/python" - <<'PY'
import json
import os
import socket
import subprocess
import traceback

try:
    import ray

    cpus = max(1, int(os.environ.get("SLURM_CPUS_PER_TASK", "1")))
    ray.init(
        num_cpus=cpus,
        num_gpus=1,
        include_dashboard=False,
        _temp_dir=os.environ["PROBE_TMP"],
        _memory=96 * 1024**3,
        object_store_memory=8 * 1024**3,
    )

    @ray.remote(num_cpus=1, num_gpus=1)
    def gpu_actor_probe():
        smi = subprocess.run(
            ["nvidia-smi", "--query-gpu=uuid,name,driver_version,memory.total", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            check=False,
        )
        return {
            "host": socket.gethostname(),
            "ray_gpu_ids": ray.get_gpu_ids(),
            "CUDA_VISIBLE_DEVICES": os.environ.get("CUDA_VISIBLE_DEVICES"),
            "nvidia_smi_exit_code": smi.returncode,
            "nvidia_smi": smi.stdout.strip(),
            "nvidia_smi_stderr": smi.stderr.strip(),
        }

    result = {
        "ray_version": ray.__version__,
        "cluster_resources": ray.cluster_resources(),
        "available_resources": ray.available_resources(),
        "gpu_task": ray.get(gpu_actor_probe.remote(), timeout=120),
    }
    resources = result["cluster_resources"]
    if resources.get("CPU") != cpus or resources.get("GPU") != 1.0:
        raise RuntimeError(f"Ray resource mismatch: {resources}")
    if resources.get("memory", 0) > 96 * 1024**3 + 16 * 1024**2:
        raise RuntimeError(f"Ray memory is not capped: {resources}")
    if resources.get("object_store_memory", 0) > 8 * 1024**3 + 16 * 1024**2:
        raise RuntimeError(f"Ray object store is not capped: {resources}")
    if result["gpu_task"]["ray_gpu_ids"] != [0] or result["gpu_task"]["nvidia_smi_exit_code"] != 0:
        raise RuntimeError(f"Ray actor did not receive the A100: {result['gpu_task']}")
    print(json.dumps(result, indent=2, sort_keys=True))
    ray.shutdown()
except Exception:
    print("RAY_GPU_PROBE_FAILED")
    traceback.print_exc()
    raise
PY
    then
        echo "ATHENA_RAY_GPU_OK=1"
    else
        echo "ATHENA_RAY_GPU_OK=0"
        exit 1
    fi
else
    echo "MISSING_VENV_PYTHON=$VENV_DIR/bin/python"
    echo "RAY_GPU_PROBE_SKIPPED=1"
    echo "ATHENA_RAY_GPU_OK=0"
    exit 1
fi

section "GPU PROBE COMPLETION"
echo "completed_at=$(date --iso-8601=seconds)"
echo "ATHENA_GPU_PROBE_COMPLETE=1"
