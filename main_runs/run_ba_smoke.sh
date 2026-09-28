#!/usr/bin/env bash
#SBATCH --job-name=ba-smoke
#SBATCH --nodes=7
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=48
#SBATCH --mem-per-cpu=2G
#SBATCH --time=00:10:00
#SBATCH --partition=plgrid
#SBATCH --account=plglscclass26-cpu

set -euo pipefail
: "${SLURM_JOB_ID:?Run under SLURM}"
: "${ISLANDS_PROJECT_DIR:?Missing absolute repository path}"
: "${ISLANDS_BA_SMOKE_DIR:?Missing absolute smoke directory}"
PROJECT_DIR=$(cd -- "$ISLANDS_PROJECT_DIR" && pwd -P)
SMOKE_DIR=$(cd -- "$ISLANDS_BA_SMOKE_DIR" && pwd -P)
VENV_DIR="${ISLANDS_VENV_DIR:-${HOME}/venvs/islands-ray}"
[[ "$PROJECT_DIR" == /* && "$SMOKE_DIR" == /* ]] || { echo "Paths must be absolute" >&2; exit 2; }

# Explicit isolation prevents inherited storage settings from writing into a
# previous campaign. The scientific runner and exporter use the same directory.
export ISLANDS_STORAGE_ROOT="$SMOKE_DIR"
export ISLANDS_RESULTS_ROOT="$SMOKE_DIR/results"
export ISLANDS_LOG_ROOT="$SMOKE_DIR/logs"
export ISLANDS_CHECKPOINT_ROOT="$SMOKE_DIR/checkpoints"
export ISLANDS_TMP_ROOT="$SMOKE_DIR/tmp"
export ISLANDS_RUN_OUTPUT_ROOT="$SMOKE_DIR/results/runs"
export ISLANDS_AUDIT_ROOT="$SMOKE_DIR/results/audit"
export ISLANDS_ARTIFACT_ROOT="$SMOKE_DIR/results/pilot_runs"
export ISLANDS_SLURM_LOG_DIR="$SMOKE_DIR/logs/slurm"
export ISLANDS_RAY_FAILURE_ROOT="$SMOKE_DIR/logs/ray_failures"
export ISLANDS_EXPORT_ROOT="$SMOKE_DIR/exports"
export ISLANDS_BUNDLE_DEFER=1
export ISLANDS_EFFECT_HORIZON_STEPS=25
export ISLANDS_DELIVERY_TIMEOUT_SECONDS=300
unset ISLANDS_RAY_FAILURE_DIR
POINTER="$SMOKE_DIR/results/job_evidence/$SLURM_JOB_ID/result_pointer.json"
JOB_DIR=$(dirname -- "$POINTER")
mkdir -p "$JOB_DIR" "$ISLANDS_EXPORT_ROOT"

cd "$PROJECT_DIR"
[[ -z "$(git status --porcelain --untracked-files=all)" ]] || {
    echo "BA smoke requires a clean checkout" >&2; exit 2;
}
module load python/3.10.4-gcccore-11.3.0
source "$VENV_DIR/bin/activate"
bash "$PROJECT_DIR/hpc_benchmarks/run_ares.sh" \
    --problem r01_elliptic --dimension 200 --islands 144 --diagnostic \
    --evaluations 128 --population 16 --offspring 4 --migrants 5 --interval 5 \
    --topology ba --strategy best --acceptance plain --repeat 1 --seed 20260912 \
    --startup-timeout 300 --actor-startup-timeout 300 --result-pointer "$POINTER"

"$VENV_DIR/bin/python" "$PROJECT_DIR/main_runs/verify_ba_smoke.py" raw \
    --smoke-dir "$SMOKE_DIR" --job-id "$SLURM_JOB_ID"
"$VENV_DIR/bin/python" "$PROJECT_DIR/hpc_benchmarks/run_bundle.py" export \
    --platform ares --job-id "$SLURM_JOB_ID" --pointer "$POINTER" \
    --job-dir "$JOB_DIR" --log-dir "$ISLANDS_SLURM_LOG_DIR" \
    --output-root "$ISLANDS_EXPORT_ROOT" --exit-code 0
"$VENV_DIR/bin/python" "$PROJECT_DIR/main_runs/verify_ba_smoke.py" bundle \
    --smoke-dir "$SMOKE_DIR" --job-id "$SLURM_JOB_ID"
echo "BA_SMOKE_OK=$SLURM_JOB_ID"
