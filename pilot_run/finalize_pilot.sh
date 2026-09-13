#!/usr/bin/env bash
#SBATCH --job-name=island-pilot-finalize
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=16G
#SBATCH --time=01:00:00
#SBATCH --partition=plgrid-testing
#SBATCH --account=plglscclass26-cpu
#SBATCH --output=/tmp/island-pilot-finalize-%j.out
#SBATCH --error=/tmp/island-pilot-finalize-%j.err

set -euo pipefail
[[ "$#" -eq 1 ]] || { echo "Usage: $0 ARRAY_JOB_ID" >&2; exit 2; }

ARRAY_JOB_ID="$1"
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PROJECT_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)
VENV_DIR="${ISLANDS_VENV_DIR:-${HOME}/venvs/islands-ray}"
source "$PROJECT_DIR/hpc_benchmarks/ares_storage.sh"
islandsea_configure_storage
ARTIFACT_ROOT="$ISLANDS_ARTIFACT_ROOT"
PILOT_DIR="$ARTIFACT_ROOT/$ARRAY_JOB_ID"

mkdir -p "$PILOT_DIR"
module load python/3.10.4-gcccore-11.3.0
source "$VENV_DIR/bin/activate"
export PYTHONPATH="$PROJECT_DIR/islands_desync${PYTHONPATH:+:$PYTHONPATH}"
export MPLBACKEND=Agg
export MPLCONFIGDIR="/tmp/${USER}/islandsea-finalize-${SLURM_JOB_ID}/matplotlib"
export TMPDIR="/tmp/${USER}/islandsea-finalize-${SLURM_JOB_ID}/tmp"
export XDG_CACHE_HOME="/tmp/${USER}/islandsea-finalize-${SLURM_JOB_ID}/xdg-cache"
mkdir -p "$MPLCONFIGDIR" "$TMPDIR" "$XDG_CACHE_HOME"
trap 'rm -rf -- "/tmp/${USER}/islandsea-finalize-${SLURM_JOB_ID}"' EXIT

sacct -n -P -j "$ARRAY_JOB_ID" \
    --format=JobIDRaw,JobName,Partition,State,ExitCode,ElapsedRaw,AllocCPUS,CPUTimeRAW,TotalCPU,MaxRSS,MaxVMSize,AveRSS,ReqMem,ConsumedEnergyRaw \
    > "$PILOT_DIR/sacct.txt" || true

cd "$PROJECT_DIR"
"$VENV_DIR/bin/python" "$SCRIPT_DIR/pilot_tools.py" finalize \
    --array-job-id "$ARRAY_JOB_ID" \
    --artifact-root "$ARTIFACT_ROOT"
