#!/usr/bin/env bash
#SBATCH --job-name=islandsea-athena-study
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --mem=128000M
#SBATCH --partition=plgrid-gpu-a100
#SBATCH --account=plgintobl-gpu-a100
#SBATCH --gres=gpu:1
#SBATCH --output=/tmp/islandsea-athena-study-%j.out
#SBATCH --error=/tmp/islandsea-athena-study-%j.err

set -euo pipefail

: "${SLURM_JOB_ID:?Submit through athena_gpu/submit_study.sh}"
: "${ISLANDS_PROJECT_DIR:?Submitter must export the repository path}"
: "${ISLANDS_VENV_DIR:?Submitter must export the Athena venv path}"
: "${ATHENA_EXPECTED_COMMIT:?Submitter must pin the Git commit}"
: "${ATHENA_STUDY_MODE:?Submitter must select canary or full}"
: "${ATHENA_STUDY_RESULT_ROOT:?Submitter must export the result root}"
: "${SCRATCH:?Athena study artifacts require SCRATCH}"

case "$ATHENA_STUDY_MODE" in
    canary|full) ;;
    *) echo "Invalid ATHENA_STUDY_MODE=$ATHENA_STUDY_MODE" >&2; exit 2 ;;
esac

PROJECT_DIR="$ISLANDS_PROJECT_DIR"
VENV_DIR="$ISLANDS_VENV_DIR"
RUN_DIR="$ATHENA_STUDY_RESULT_ROOT/$SLURM_JOB_ID"
RAY_TMP_DIR="/tmp/r${SLURM_JOB_ID}"
PYTHON_JOB_PID=""

[[ "$RAY_TMP_DIR" =~ ^/tmp/r[0-9]+$ ]] || { echo "Unsafe Ray tmp path" >&2; exit 2; }
[[ -f "$PROJECT_DIR/athena_gpu/run_study.py" ]] || { echo "Invalid project directory" >&2; exit 2; }
[[ -x "$VENV_DIR/bin/python" ]] || { echo "Missing Athena venv: $VENV_DIR" >&2; exit 2; }

SCRATCH_REAL=$(realpath -m -- "$SCRATCH")
case "$(realpath -m -- "$RUN_DIR")/" in
    "$SCRATCH_REAL"/*) ;;
    *) echo "Result directory must remain below SCRATCH" >&2; exit 2 ;;
esac
[[ ! -L "$RAY_TMP_DIR" ]] || { echo "Ray tmp cannot be a symlink" >&2; exit 2; }
mkdir -p "$RUN_DIR/cache/cupy" "$RUN_DIR/cache/xdg" "$RUN_DIR/tmp" "$RAY_TMP_DIR"

cleanup() {
    local status=$?
    trap - EXIT INT TERM
    if [[ "$PYTHON_JOB_PID" =~ ^[0-9]+$ ]]; then
        kill -TERM -- "-$PYTHON_JOB_PID" 2>/dev/null || true
    fi
    if [[ "$status" -ne 0 && -d "$RAY_TMP_DIR/session_latest/logs" ]]; then
        cp -a -- "$RAY_TMP_DIR/session_latest/logs" "$RUN_DIR/ray-failure-logs" || true
    fi
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

export ISLANDS_STORAGE_ROOT="${ISLANDS_STORAGE_ROOT:-$SCRATCH/islandsEA}"
export ISLANDS_RESULTS_ROOT="${ISLANDS_RESULTS_ROOT:-$ISLANDS_STORAGE_ROOT/results}"
export ISLANDS_LOG_ROOT="${ISLANDS_LOG_ROOT:-$ISLANDS_STORAGE_ROOT/logs}"
export ISLANDS_RUN_OUTPUT_ROOT="${ISLANDS_RUN_OUTPUT_ROOT:-$ISLANDS_RESULTS_ROOT/runs}"
export ISLANDS_AUDIT_ROOT="${ISLANDS_AUDIT_ROOT:-$ISLANDS_RESULTS_ROOT/audit}"
export ISLANDS_ARTIFACT_ROOT="${ISLANDS_ARTIFACT_ROOT:-$ISLANDS_RESULTS_ROOT/pilot_runs}"
export ISLANDS_SLURM_LOG_DIR="${ISLANDS_SLURM_LOG_DIR:-$ISLANDS_LOG_ROOT/slurm}"
export ISLANDS_CHECKPOINT_ROOT="${ISLANDS_CHECKPOINT_ROOT:-$ISLANDS_STORAGE_ROOT/checkpoints}"
export ISLANDS_TMP_ROOT="${ISLANDS_TMP_ROOT:-$ISLANDS_STORAGE_ROOT/tmp}"
export TMPDIR="$RUN_DIR/tmp"
export XDG_CACHE_HOME="$RUN_DIR/cache/xdg"
export CUPY_CACHE_DIR="$RUN_DIR/cache/cupy"
export PYTHONPATH="$PROJECT_DIR:$PROJECT_DIR/islands_desync${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export MPLBACKEND=Agg
export MPLCONFIGDIR="$RUN_DIR/cache/matplotlib"
export RAY_DEDUP_LOGS=0
mkdir -p "$MPLCONFIGDIR" "$ISLANDS_RUN_OUTPUT_ROOT" "$ISLANDS_AUDIT_ROOT"

cd "$PROJECT_DIR"
ACTUAL_COMMIT=$(git rev-parse HEAD)
[[ "$ACTUAL_COMMIT" == "$ATHENA_EXPECTED_COMMIT" ]] || {
    echo "Checkout changed after submission: expected $ATHENA_EXPECTED_COMMIT, got $ACTUAL_COMMIT" >&2
    exit 2
}
[[ -z "$(git status --porcelain --untracked-files=all)" ]] || {
    echo "Checkout became dirty after submission" >&2
    git status --short >&2
    exit 2
}

case "$(hostname -s)" in
    login*) echo "Refusing to run a study job on a login node" >&2; exit 2 ;;
esac
[[ -n "${CUDA_VISIBLE_DEVICES:-}" ]] || { echo "CUDA_VISIBLE_DEVICES is empty" >&2; exit 2; }

"$VENV_DIR/bin/python" "$PROJECT_DIR/athena_gpu/environment_contract.py" \
    --output "$RUN_DIR/environment-check.json"
"$VENV_DIR/bin/python" -m pip check
"$VENV_DIR/bin/python" -m pip freeze > "$RUN_DIR/pip-freeze.txt"
nvidia-smi --query-gpu=index,uuid,name,driver_version,memory.total --format=csv \
    > "$RUN_DIR/nvidia-smi.csv"

COMMON_ARGS=(
    --problem r01_elliptic
    --dimension 200
    --population 16
    --offspring 4
    --migrants 5
    --interval 5
    --topology torus
    --strategy best
    --acceptance plain
    --repeat 1
    --seed 20260912
    --ray-address local
    --local-cpus 15
    --ray-temp-dir "$RAY_TMP_DIR"
    --ray-memory-gib 96
    --object-store-gib 8
    --result-pointer "$RUN_DIR/result_pointer.json"
)

if [[ "$ATHENA_STUDY_MODE" == canary ]]; then
    MODE_ARGS=(
        --diagnostic
        --islands 12
        --shards 4
        --evaluations 128
        --torus-rows 3
        --torus-columns 4
        --operation-timeout-seconds 30
        --actor-startup-timeout 90
        --run-timeout-seconds 300
        --finalization-timeout-seconds 60
    )
else
    MODE_ARGS=(
        --islands 144
        --shards 12
        --evaluations 8000
        --torus-rows 12
        --torus-columns 12
        --operation-timeout-seconds 180
        --actor-startup-timeout 300
        --run-timeout-seconds 4200
        --finalization-timeout-seconds 600
        --confirm-study-144
    )
fi

echo "=== ATHENA SHARDED STUDY RUN ==="
echo "mode=$ATHENA_STUDY_MODE"
echo "job_id=$SLURM_JOB_ID"
echo "host=$(hostname -f)"
echo "commit=$ACTUAL_COMMIT"
echo "result_dir=$RUN_DIR"
echo "ray_tmp=$RAY_TMP_DIR"
echo "cuda_visible_devices=$CUDA_VISIBLE_DEVICES"

command -v setsid >/dev/null || { echo "setsid is required" >&2; exit 2; }
setsid "$VENV_DIR/bin/python" -u "$PROJECT_DIR/athena_gpu/run_study.py" \
    "${COMMON_ARGS[@]}" "${MODE_ARGS[@]}" &
PYTHON_JOB_PID=$!
wait "$PYTHON_JOB_PID"
PYTHON_JOB_PID=""

"$VENV_DIR/bin/python" -u "$PROJECT_DIR/athena_gpu/validate_study_run.py" \
    --pointer "$RUN_DIR/result_pointer.json" \
    --output "$RUN_DIR/validation.json" \
    --mode "$ATHENA_STUDY_MODE" \
    --expected-commit "$ACTUAL_COMMIT"

echo "ATHENA_STUDY_RESULT=$RUN_DIR"
echo "ATHENA_STUDY_JOB_OK=1"
