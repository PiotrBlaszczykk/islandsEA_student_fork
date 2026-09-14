#!/usr/bin/env bash
#SBATCH --job-name=islandsea-athena-gpu-ready
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=128000M
#SBATCH --time=00:15:00
#SBATCH --partition=plgrid-gpu-a100
#SBATCH --account=plgintobl-gpu-a100
#SBATCH --gres=gpu:1
#SBATCH --output=/tmp/islandsea-athena-gpu-ready-%j.out
#SBATCH --error=/tmp/islandsea-athena-gpu-ready-%j.err

set -euo pipefail

: "${SLURM_JOB_ID:?Submit through athena_gpu/submit_readiness.sh}"
: "${ISLANDS_PROJECT_DIR:?Submitter must export the absolute repository path}"
: "${ISLANDS_VENV_DIR:?Submitter must export the Athena venv path}"
: "${ATHENA_READINESS_ROOT:?Submitter must export the result root}"
: "${ATHENA_EXPECTED_COMMIT:?Submitter must pin the Git commit}"

PROJECT_DIR="$ISLANDS_PROJECT_DIR"
SCRIPT_DIR="$PROJECT_DIR/athena_gpu"
VENV_DIR="$ISLANDS_VENV_DIR"
RUN_DIR="$ATHENA_READINESS_ROOT/$SLURM_JOB_ID"
RAY_TMP_DIR="/tmp/r${SLURM_JOB_ID}"

[[ "$RAY_TMP_DIR" =~ ^/tmp/r[0-9]+$ ]] || {
    echo "Unsafe Ray tmp path: $RAY_TMP_DIR" >&2
    exit 2
}
[[ -f "$SCRIPT_DIR/gpu_readiness.py" ]] || {
    echo "Invalid ISLANDS_PROJECT_DIR: $PROJECT_DIR" >&2
    exit 2
}
[[ -x "$VENV_DIR/bin/python" ]] || { echo "Missing venv: $VENV_DIR" >&2; exit 2; }

mkdir -p "$RUN_DIR" "$RAY_TMP_DIR/tmp" "$RAY_TMP_DIR/xdg-cache" "$RAY_TMP_DIR/cupy-cache"
cleanup() {
    local status=$?
    trap - EXIT INT TERM
    "$VENV_DIR/bin/ray" stop --force >/dev/null 2>&1 || true
    if [[ "$RAY_TMP_DIR" =~ ^/tmp/r[0-9]+$ ]]; then
        rm -rf -- "$RAY_TMP_DIR"
    fi
    exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

module load Python/3.10.4
module load CUDA/11.7.0
source "$VENV_DIR/bin/activate"

export TMPDIR="$RAY_TMP_DIR/tmp"
export XDG_CACHE_HOME="$RAY_TMP_DIR/xdg-cache"
export CUPY_CACHE_DIR="$RAY_TMP_DIR/cupy-cache"
export PYTHONPATH="$PROJECT_DIR/islands_desync${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export RAY_DEDUP_LOGS=0

cd "$PROJECT_DIR"
ACTUAL_COMMIT=$(git rev-parse HEAD)
[[ "$ACTUAL_COMMIT" == "$ATHENA_EXPECTED_COMMIT" ]] || {
    echo "Checkout changed after submission: expected $ATHENA_EXPECTED_COMMIT, found $ACTUAL_COMMIT" >&2
    exit 2
}
[[ -z "$(git status --porcelain --untracked-files=all)" ]] || {
    echo "Checkout became dirty after submission." >&2
    git status --short >&2
    exit 2
}

echo "=== ATHENA GPU READINESS ==="
echo "job_id=$SLURM_JOB_ID"
echo "host=$(hostname -f)"
echo "commit=$ACTUAL_COMMIT"
echo "venv=$VENV_DIR"
echo "result_dir=$RUN_DIR"
echo "ray_tmp=$RAY_TMP_DIR"
echo "cpus=${SLURM_CPUS_PER_TASK:-UNSET}"
echo "cuda_visible_devices=${CUDA_VISIBLE_DEVICES:-UNSET}"

case "$(hostname -s)" in
    login*) echo "Refusing to run a GPU readiness test on a login node." >&2; exit 2 ;;
esac
[[ -n "${CUDA_VISIBLE_DEVICES:-}" ]] || { echo "CUDA_VISIBLE_DEVICES is empty." >&2; exit 2; }
nvidia-smi --query-gpu=index,uuid,name,driver_version,memory.total --format=csv \
    | tee "$RUN_DIR/nvidia-smi.csv"

# Keep the legacy NumPy/SciPy stack intact. CuPy 10.6 is the last line whose
# compatibility matrix is based on NumPy 1.21/SciPy 1.7 and has a CPython 3.10
# wheel dedicated to CUDA 11.7.
command -v flock >/dev/null || { echo "flock is required for safe venv bootstrap." >&2; exit 2; }
exec 9>"$VENV_DIR/.athena-cupy-bootstrap.lock"
flock -n 9 || {
    echo "Another Athena job is modifying the GPU venv; refusing concurrent installation." >&2
    exit 2
}
CUPY_STATE=$("$VENV_DIR/bin/python" - <<'PY'
import importlib.metadata

matches = []
for distribution in importlib.metadata.distributions():
    name = (distribution.metadata.get("Name") or "").lower()
    if name == "cupy" or name.startswith("cupy-cuda"):
        matches.append((name, distribution.version))
if not matches:
    print("missing")
elif matches == [("cupy-cuda117", "10.6.0")]:
    print("ready")
else:
    print("conflict:" + ",".join(f"{name}=={version}" for name, version in matches))
PY
)
case "$CUPY_STATE" in
    missing)
        echo "Installing pinned cupy-cuda117==10.6.0 into $VENV_DIR"
        "$VENV_DIR/bin/python" -m pip install --only-binary=:all: "cupy-cuda117==10.6.0"
        ;;
    ready)
        echo "Pinned CuPy is already installed."
        ;;
    *)
        echo "Refusing mixed or unexpected CuPy installation: $CUPY_STATE" >&2
        exit 2
        ;;
esac

"$VENV_DIR/bin/python" -m pip check
"$VENV_DIR/bin/python" -m pip freeze > "$RUN_DIR/pip-freeze.txt"

"$VENV_DIR/bin/python" -u "$SCRIPT_DIR/gpu_readiness.py" \
    --project-dir "$PROJECT_DIR" \
    --output "$RUN_DIR/readiness.json" \
    --ray-temp-dir "$RAY_TMP_DIR" \
    --ray-memory-gib 96 \
    --object-store-gib 8

echo "ATHENA_GPU_READINESS_RESULT=$RUN_DIR/readiness.json"
echo "ATHENA_GPU_READINESS_OK=1"
