#!/usr/bin/env bash
#SBATCH --job-name=complete-best-recover
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=01:00:00
#SBATCH --partition=plgrid
#SBATCH --account=plglscclass26-cpu

set -euo pipefail
: "${ISLANDS_PROJECT_DIR:?Missing absolute repository path}"
: "${ISLANDS_CAMPAIGN_DIR:?Missing absolute campaign path}"
: "${SLURM_ARRAY_TASK_ID:?Run as a recovery array task}"
: "${SLURM_JOB_ID:?Missing recovery job ID}"
VENV_DIR="${ISLANDS_VENV_DIR:-${HOME}/venvs/islands-ray}"

cd "$ISLANDS_PROJECT_DIR"
module load python/3.10.4-gcccore-11.3.0
source "$VENV_DIR/bin/activate"
export ISLANDS_CAMPAIGN_TOPOLOGY=complete
export ISLANDS_CAMPAIGN_STRATEGY=best
"$VENV_DIR/bin/python" main_runs/recover_complete_best.py task \
    --campaign-dir "$ISLANDS_CAMPAIGN_DIR" \
    --task-id "$SLURM_ARRAY_TASK_ID" --recovery-job-id "$SLURM_JOB_ID"
