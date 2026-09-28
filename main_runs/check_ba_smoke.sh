#!/usr/bin/env bash
# Run on the login node after the one BA smoke job leaves squeue.
set -euo pipefail
[[ "$#" -eq 1 && "$1" =~ ^[0-9]+$ ]] || { echo "Usage: $0 JOB_ID" >&2; exit 2; }
: "${SCRATCH:?SCRATCH must be available on Ares}"
JOB_ID="$1"
STATE=$(sacct -n -X -P -j "$JOB_ID" --format=State,ExitCode | head -n 1)
[[ "$STATE" == 'COMPLETED|0:0' ]] || {
    echo "BA smoke job $JOB_ID is not complete: $STATE" >&2; exit 1;
}
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PROJECT_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd -P)
VENV_DIR="${ISLANDS_VENV_DIR:-${HOME}/venvs/islands-ray}"
cd "$PROJECT_DIR"
module load python/3.10.4-gcccore-11.3.0
source "$VENV_DIR/bin/activate"
"$VENV_DIR/bin/python" "$SCRIPT_DIR/verify_ba_smoke.py" bundle \
    --smoke-dir "$SCRATCH/ba_smoke" --job-id "$JOB_ID"
grep -F "BA_SMOKE_OK=$JOB_ID" "$SCRATCH/ba_smoke/logs/slurm/ba-smoke-${JOB_ID}.out"
echo "BA_SMOKE_CONFIRMED=$JOB_ID"
