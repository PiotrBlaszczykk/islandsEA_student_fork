#!/usr/bin/env bash
#SBATCH --job-name=islandsea-validation
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:05:00
#SBATCH --output=/tmp/islandsea-validation-%j.out
#SBATCH --error=/tmp/islandsea-validation-%j.err
set -euo pipefail
: "${SLURM_JOB_ID:?Submit with sbatch from the repository root}"
PROJECT_DIR="${ISLANDS_PROJECT_DIR:-${SLURM_SUBMIT_DIR}}"
VENV_DIR="${ISLANDS_VENV_DIR:-${HOME}/venvs/islands-ray}"
source "$PROJECT_DIR/hpc_benchmarks/ares_storage.sh"
islandsea_configure_storage
module load python/3.10.4-gcccore-11.3.0
source "$VENV_DIR/bin/activate"
export PYTHONPATH="$PROJECT_DIR/islands_desync${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 MPLBACKEND=Agg
VALIDATION_TMP="/tmp/${USER}/islandsea-validation-${SLURM_JOB_ID}"
export MPLCONFIGDIR="$VALIDATION_TMP/matplotlib"
export TMPDIR="$VALIDATION_TMP/tmp"
export XDG_CACHE_HOME="$VALIDATION_TMP/xdg-cache"
mkdir -p "$MPLCONFIGDIR" "$TMPDIR" "$XDG_CACHE_HOME" "$ISLANDS_RESULTS_ROOT/validation"
cleanup() {
    if [[ "$VALIDATION_TMP" == "/tmp/${USER}/islandsea-validation-${SLURM_JOB_ID}" ]]; then
        rm -rf -- "$VALIDATION_TMP"
    fi
}
trap cleanup EXIT
cd "$PROJECT_DIR"
srun python -m unittest discover -s hpc_benchmarks -p test_study_topologies.py
srun python -m unittest pilot_run.test_spool_paths
srun python -m unittest pilot_run.test_pilot_tools
cd "$PROJECT_DIR/islands_desync"
srun python -m islands_desync.geneticAlgorithm.utils.benchmarks_refined --validate \
    --output "$ISLANDS_RESULTS_ROOT/validation/validation-${SLURM_JOB_ID}.json"
