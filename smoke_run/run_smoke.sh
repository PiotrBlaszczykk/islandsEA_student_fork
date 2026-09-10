#!/usr/bin/env bash
#SBATCH --job-name=islandsea-smoke
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:05:00
#SBATCH --output=slurm-%j.out

set -euo pipefail

VENV_DIR="/net/people/plgrid/plgblaszczykk/venvs/islands-ray"
SCRIPT_DIR="${SLURM_SUBMIT_DIR:-$(pwd)}"
JOB_TOKEN="${SLURM_JOB_ID:-manual-$$}"
RAY_TMP_DIR="/tmp/${USER}/islandsea-smoke-${JOB_TOKEN}"

module load python/3.10.4-gcccore-11.3.0

if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
    echo "ERROR: brak interpretera ${VENV_DIR}/bin/python" >&2
    echo "Uruchom najpierw: bash setup_ares_venv.sh" >&2
    exit 1
fi

mkdir -p "${RAY_TMP_DIR}"

echo "SLURM_JOB_ID=${SLURM_JOB_ID:-brak}"
echo "SLURMD_NODENAME=${SLURMD_NODENAME:-brak}"
echo "VENV_DIR=${VENV_DIR}"
echo "RAY_TMP_DIR=${RAY_TMP_DIR}"

cd "${SCRIPT_DIR}"

srun --ntasks=1 "${VENV_DIR}/bin/python" -u smoke.py \
    --expected-venv "${VENV_DIR}" \
    --ray-temp-dir "${RAY_TMP_DIR}"
