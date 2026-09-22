#!/usr/bin/env bash
#SBATCH --job-name=torus-best
#SBATCH --nodes=7
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=48
#SBATCH --mem-per-cpu=2G
#SBATCH --time=01:00:00
#SBATCH --partition=plgrid
#SBATCH --account=plglscclass26-cpu
#SBATCH --output=/tmp/torus-best-%A_%a.out
#SBATCH --error=/tmp/torus-best-%A_%a.err

set -euo pipefail
: "${SLURM_JOB_ID:?This file must run as a SLURM array task}"
: "${SLURM_ARRAY_JOB_ID:?Missing SLURM_ARRAY_JOB_ID}"
: "${SLURM_ARRAY_TASK_ID:?Missing SLURM_ARRAY_TASK_ID}"
: "${ISLANDS_PROJECT_DIR:?Missing absolute repository path}"
: "${ISLANDS_CAMPAIGN_DIR:?Missing absolute campaign path}"

case "$ISLANDS_PROJECT_DIR:$ISLANDS_CAMPAIGN_DIR" in
    /*:/*) ;;
    *) echo "Project and campaign paths must be absolute" >&2; exit 2 ;;
esac
PROJECT_DIR=$(cd -- "$ISLANDS_PROJECT_DIR" && pwd -P)
CAMPAIGN_DIR=$(cd -- "$ISLANDS_CAMPAIGN_DIR" && pwd -P)
TOOLS="$PROJECT_DIR/main_runs/campaign_tools.py"
PLAN="$CAMPAIGN_DIR/campaign_plan.json"
VENV_DIR="${ISLANDS_VENV_DIR:-${HOME}/venvs/islands-ray}"
TASK_DIR="$CAMPAIGN_DIR/tasks/task-$(printf '%03d' "$SLURM_ARRAY_TASK_ID")"
POINTER="$TASK_DIR/result_pointer.json"
VERIFICATION="$TASK_DIR/bundle_verification.json"

[[ -f "$TOOLS" && -f "$PLAN" && -x "$VENV_DIR/bin/python" ]] || {
    echo "Missing campaign code, plan or Ares venv" >&2
    exit 2
}
cd "$PROJECT_DIR"
[[ -z "$(git status --porcelain --untracked-files=all)" ]] || {
    echo "Campaign task blocked: checkout is dirty" >&2
    git status --short >&2
    exit 2
}

export ISLANDS_STORAGE_ROOT="$CAMPAIGN_DIR/storage"
export ISLANDS_RESULTS_ROOT="$ISLANDS_STORAGE_ROOT/results"
export ISLANDS_LOG_ROOT="$CAMPAIGN_DIR/logs"
export ISLANDS_CHECKPOINT_ROOT="$ISLANDS_STORAGE_ROOT/checkpoints"
export ISLANDS_TMP_ROOT="$ISLANDS_STORAGE_ROOT/tmp"
export ISLANDS_RUN_OUTPUT_ROOT="$ISLANDS_RESULTS_ROOT/runs"
export ISLANDS_AUDIT_ROOT="$ISLANDS_RESULTS_ROOT/audit"
export ISLANDS_ARTIFACT_ROOT="$ISLANDS_RESULTS_ROOT/pilot_runs"
export ISLANDS_SLURM_LOG_DIR="$CAMPAIGN_DIR/logs"
export ISLANDS_RAY_FAILURE_ROOT="$CAMPAIGN_DIR/ray_failures"
export ISLANDS_EXPORT_ROOT="$CAMPAIGN_DIR/runs"
export ISLANDS_EFFECT_HORIZON_STEPS=25
export ISLANDS_DELIVERY_TIMEOUT_SECONDS=300
export ISLANDS_BUNDLE_DEFER=1
mkdir -p "$TASK_DIR" "$ISLANDS_SLURM_LOG_DIR" "$ISLANDS_EXPORT_ROOT"

module load python/3.10.4-gcccore-11.3.0
source "$VENV_DIR/bin/activate"
mapfile -t TASK < <(
    "$VENV_DIR/bin/python" "$TOOLS" task --plan "$PLAN" --task-id "$SLURM_ARRAY_TASK_ID"
)
[[ "${#TASK[@]}" -eq 3 ]] || { echo "Invalid task mapping" >&2; exit 2; }
BENCHMARK="${TASK[0]}"
DIMENSION="${TASK[1]}"
REPEAT="${TASK[2]}"

"$VENV_DIR/bin/python" "$TOOLS" record-task \
    --plan "$PLAN" --campaign-dir "$CAMPAIGN_DIR" \
    --task-id "$SLURM_ARRAY_TASK_ID" --status running \
    --job-id "$SLURM_JOB_ID" --array-job-id "$SLURM_ARRAY_JOB_ID" --exit-code 0

echo "CAMPAIGN_TASK task=$SLURM_ARRAY_TASK_ID benchmark=$BENCHMARK dimension=$DIMENSION repeat=$REPEAT job=$SLURM_JOB_ID"
set +e
bash "$PROJECT_DIR/hpc_benchmarks/run_ares.sh" \
    --problem "$BENCHMARK" \
    --dimension "$DIMENSION" \
    --islands 144 \
    --evaluations 8000 \
    --population 16 \
    --offspring 4 \
    --migrants 5 \
    --interval 5 \
    --topology torus \
    --torus-rows 12 \
    --torus-columns 12 \
    --strategy best \
    --acceptance plain \
    --repeat "$REPEAT" \
    --seed 20260912 \
    --startup-timeout 300 \
    --actor-startup-timeout 300 \
    --result-pointer "$POINTER"
STATUS=$?
set -e

if (( STATUS == 0 )); then
    set +e
    "$VENV_DIR/bin/python" "$TOOLS" validate-run \
        --plan "$PLAN" --campaign-dir "$CAMPAIGN_DIR" \
        --task-id "$SLURM_ARRAY_TASK_ID" \
        --job-id "$SLURM_JOB_ID" --array-job-id "$SLURM_ARRAY_JOB_ID"
    STATUS=$?
    set -e
fi

# run_ares.sh has already stopped Ray and retained all original files. Package
# only after scientific validation, so validation.json is inside the bundle.
source "$PROJECT_DIR/hpc_benchmarks/run_bundle.sh"
islandsea_bundle_prepare ares --result-pointer "$POINTER"
set +e
islandsea_bundle_finish "$STATUS"
BUNDLE_STATUS=$?
set -e
if (( STATUS == 0 && BUNDLE_STATUS != 0 )); then STATUS="$BUNDLE_STATUS"; fi

ARCHIVE="$ISLANDS_EXPORT_ROOT/run_${SLURM_JOB_ID}.tar.gz"
if (( STATUS == 0 )); then
    set +e
    "$VENV_DIR/bin/python" "$PROJECT_DIR/hpc_benchmarks/run_bundle.py" verify "$ARCHIVE" > "$VERIFICATION"
    VERIFY_STATUS=$?
    set -e
    if (( VERIFY_STATUS != 0 )); then
        echo "Bundle verification failed for $ARCHIVE" >&2
        STATUS="$VERIFY_STATUS"
    fi
fi

if (( STATUS == 0 )); then
    "$VENV_DIR/bin/python" "$TOOLS" record-task \
        --plan "$PLAN" --campaign-dir "$CAMPAIGN_DIR" \
        --task-id "$SLURM_ARRAY_TASK_ID" --status completed \
        --job-id "$SLURM_JOB_ID" --array-job-id "$SLURM_ARRAY_JOB_ID" --exit-code 0 \
        --archive "$ARCHIVE" --verification "$VERIFICATION"
    echo "CAMPAIGN_TASK_OK=$SLURM_ARRAY_TASK_ID"
else
    "$VENV_DIR/bin/python" "$TOOLS" record-task \
        --plan "$PLAN" --campaign-dir "$CAMPAIGN_DIR" \
        --task-id "$SLURM_ARRAY_TASK_ID" --status failed \
        --job-id "$SLURM_JOB_ID" --array-job-id "$SLURM_ARRAY_JOB_ID" --exit-code "$STATUS" \
        --archive "$ARCHIVE"
    echo "CAMPAIGN_TASK_FAILED=$SLURM_ARRAY_TASK_ID status=$STATUS" >&2
fi
exit "$STATUS"
