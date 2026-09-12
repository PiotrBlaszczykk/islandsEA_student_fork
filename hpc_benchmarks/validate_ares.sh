#!/usr/bin/env bash
#SBATCH --job-name=islandsea-validation
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:05:00
#SBATCH --output=slurm-%j.out
set -euo pipefail
: "${SLURM_JOB_ID:?Submit with sbatch from the repository root}"
PROJECT_DIR="${ISLANDS_PROJECT_DIR:-${SLURM_SUBMIT_DIR}}"
VENV_DIR="${ISLANDS_VENV_DIR:-${HOME}/venvs/islands-ray}"
module load python/3.10.4-gcccore-11.3.0
source "$VENV_DIR/bin/activate"
export PYTHONPATH="$PROJECT_DIR/islands_desync${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 MPLBACKEND=Agg
export MPLCONFIGDIR="/tmp/${USER}/islandsea-validation-${SLURM_JOB_ID}/matplotlib"
mkdir -p "$MPLCONFIGDIR" "$PROJECT_DIR/hpc_benchmarks/results"
cd "$PROJECT_DIR/islands_desync"
srun python -m islands_desync.geneticAlgorithm.utils.benchmarks_refined --validate \
    --output "$PROJECT_DIR/hpc_benchmarks/results/validation-${SLURM_JOB_ID}.json"
