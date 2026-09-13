#!/usr/bin/env bash
#SBATCH --job-name=islandsea-smoke
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:05:00
#SBATCH --output=/tmp/islandsea-smoke-%j.out
#SBATCH --error=/tmp/islandsea-smoke-%j.err

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PROJECT_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)
VENV_DIR="${ISLANDS_VENV_DIR:-${HOME}/venvs/islands-ray}"
source "$PROJECT_DIR/hpc_benchmarks/ares_storage.sh"
islandsea_configure_storage
JOB_TOKEN="${SLURM_JOB_ID:-manual-$$}"
RAY_TMP_DIR="/tmp/${USER}/islandsea-smoke-${JOB_TOKEN}"
export TMPDIR="${RAY_TMP_DIR}/tmp"
export XDG_CACHE_HOME="${RAY_TMP_DIR}/xdg-cache"

module load python/3.10.4-gcccore-11.3.0

if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
    echo "ERROR: brak interpretera ${VENV_DIR}/bin/python" >&2
    echo "Uruchom najpierw: bash setup_ares_venv.sh" >&2
    exit 1
fi

mkdir -p "${TMPDIR}" "${XDG_CACHE_HOME}"
cleanup() {
    if [[ "$RAY_TMP_DIR" == "/tmp/${USER}/islandsea-smoke-${JOB_TOKEN}" ]]; then
        rm -rf -- "$RAY_TMP_DIR"
    fi
}
trap cleanup EXIT

echo "SLURM_JOB_ID=${SLURM_JOB_ID:-brak}"
echo "SLURMD_NODENAME=${SLURMD_NODENAME:-brak}"
echo "VENV_DIR=${VENV_DIR}"
echo "RAY_TMP_DIR=${RAY_TMP_DIR}"

cd "${SCRIPT_DIR}"

srun --ntasks=1 "${VENV_DIR}/bin/python" -u smoke.py \
    --expected-venv "${VENV_DIR}" \
    --ray-temp-dir "${RAY_TMP_DIR}"
