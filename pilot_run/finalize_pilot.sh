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
: "${PILOT_EXPECTED_COMMIT:?Missing pinned pilot commit}"
: "${ISLANDS_PROJECT_DIR:?Missing absolute repository path}"

ARRAY_JOB_ID="$1"
case "$ISLANDS_PROJECT_DIR" in
    /*|[A-Za-z]:/*) ;;
    *) echo "ISLANDS_PROJECT_DIR must be an absolute path: $ISLANDS_PROJECT_DIR" >&2; exit 2 ;;
esac
PROJECT_DIR=$(cd -- "$ISLANDS_PROJECT_DIR" && pwd -P) || {
    echo "Invalid ISLANDS_PROJECT_DIR: $ISLANDS_PROJECT_DIR" >&2
    exit 2
}
[[ -f "$PROJECT_DIR/pilot_run/pilot_spec.json" \
    && -f "$PROJECT_DIR/hpc_benchmarks/ares_storage.sh" ]] || {
    echo "ISLANDS_PROJECT_DIR does not point to an IslandsEA checkout: $PROJECT_DIR" >&2
    exit 2
}
export ISLANDS_PROJECT_DIR="$PROJECT_DIR"
SCRIPT_DIR="$PROJECT_DIR/pilot_run"
VENV_DIR="${ISLANDS_VENV_DIR:-${HOME}/venvs/islands-ray}"
source "$PROJECT_DIR/hpc_benchmarks/ares_storage.sh"
islandsea_configure_storage
ARTIFACT_ROOT="$ISLANDS_ARTIFACT_ROOT"
PILOT_DIR="$ARTIFACT_ROOT/$ARRAY_JOB_ID"

mkdir -p "$PILOT_DIR"
module load python/3.10.4-gcccore-11.3.0
source "$VENV_DIR/bin/activate"
cd "$PROJECT_DIR"
ACTUAL_COMMIT=$(git rev-parse HEAD)
[[ "$ACTUAL_COMMIT" == "$PILOT_EXPECTED_COMMIT" ]] || {
    echo "Finalizer blocked: expected commit $PILOT_EXPECTED_COMMIT, found $ACTUAL_COMMIT." >&2
    exit 2
}
[[ -z "$(git status --porcelain --untracked-files=all)" ]] || {
    echo "Finalizer blocked: checkout became dirty after submission." >&2
    git status --short >&2
    exit 2
}
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

"$VENV_DIR/bin/python" "$SCRIPT_DIR/pilot_tools.py" finalize \
    --array-job-id "$ARRAY_JOB_ID" \
    --artifact-root "$ARTIFACT_ROOT"
