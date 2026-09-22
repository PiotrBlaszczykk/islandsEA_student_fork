#!/usr/bin/env bash

# Explicitly retry one failed element of an existing torus_best campaign and
# then re-run its fail-closed finalizer. Run this file on the login node.
set -euo pipefail
[[ "$#" -eq 1 && "$1" =~ ^([1-9]|[1-9][0-9]|1[01][0-9]|120)$ ]] || {
    echo "Usage: $0 TASK_ID (1..120)" >&2
    exit 2
}
TASK_ID="$1"
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PROJECT_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd -P)
VENV_DIR="${ISLANDS_VENV_DIR:-${HOME}/venvs/islands-ray}"
: "${SCRATCH:?SCRATCH must be available on Ares}"
CAMPAIGN_DIR="${TORUS_BEST_CAMPAIGN_DIR:-$SCRATCH/torus_best}"

cd "$PROJECT_DIR"
[[ "$(git branch --show-current)" == "summer_ares_blaszczyk" ]] || {
    echo "Use branch summer_ares_blaszczyk on Ares" >&2
    exit 2
}
[[ -z "$(git status --porcelain --untracked-files=all)" ]] || {
    echo "Commit or remove local changes before retrying" >&2
    exit 2
}
[[ -x "$VENV_DIR/bin/python" && -f "$CAMPAIGN_DIR/submission.json" ]] || {
    echo "Existing campaign or Ares venv is missing" >&2
    exit 2
}
[[ ! -e "$CAMPAIGN_DIR/torus_best.tar.gz" ]] || {
    echo "Campaign archive already exists; refusing to modify a finalized campaign" >&2
    exit 2
}

module load python/3.10.4-gcccore-11.3.0
source "$VENV_DIR/bin/activate"
read -r CAMPAIGN_ARRAY_JOB_ID STATUS < <(
    "$VENV_DIR/bin/python" -c '
import json, pathlib, sys
root, task = pathlib.Path(sys.argv[1]), int(sys.argv[2])
submission = json.loads((root / "submission.json").read_text())
record = json.loads((root / "tasks" / f"task-{task:03d}" / "task.json").read_text())
print(submission["array_job_id"], record["status"])
' "$CAMPAIGN_DIR" "$TASK_ID"
)
[[ "$STATUS" == "failed" ]] || {
    echo "Task $TASK_ID is not recorded as failed (status=$STATUS)" >&2
    exit 2
}

RETRY_SUBMISSION=$(sbatch --parsable \
    --array="$TASK_ID" \
    --output="$CAMPAIGN_DIR/logs/torus-best-retry-%A_%a.out" \
    --error="$CAMPAIGN_DIR/logs/torus-best-retry-%A_%a.err" \
    --export="ALL,ISLANDS_PROJECT_DIR=${PROJECT_DIR},ISLANDS_CAMPAIGN_DIR=${CAMPAIGN_DIR},ISLANDS_VENV_DIR=${VENV_DIR},ISLANDS_CAMPAIGN_ARRAY_JOB_ID=${CAMPAIGN_ARRAY_JOB_ID}" \
    "$SCRIPT_DIR/run_torus_best_array.sh")
RETRY_ARRAY_JOB_ID="${RETRY_SUBMISSION%%;*}"

FINALIZER_SUBMISSION=$(sbatch --parsable \
    --dependency="afterany:${RETRY_ARRAY_JOB_ID}" \
    --output="$CAMPAIGN_DIR/logs/torus-best-finalize-%j.out" \
    --error="$CAMPAIGN_DIR/logs/torus-best-finalize-%j.err" \
    --export="ALL,ISLANDS_PROJECT_DIR=${PROJECT_DIR},ISLANDS_CAMPAIGN_DIR=${CAMPAIGN_DIR},ISLANDS_VENV_DIR=${VENV_DIR}" \
    "$SCRIPT_DIR/finalize_torus_best.sh" "$CAMPAIGN_ARRAY_JOB_ID" "$RETRY_ARRAY_JOB_ID")
FINALIZER_JOB_ID="${FINALIZER_SUBMISSION%%;*}"

cat <<EOF
TORUS_BEST_RETRY_TASK=$TASK_ID
TORUS_BEST_RETRY_ARRAY_JOB_ID=$RETRY_ARRAY_JOB_ID
TORUS_BEST_RETRY_FINALIZER_JOB_ID=$FINALIZER_JOB_ID
Monitor: squeue -j $RETRY_ARRAY_JOB_ID,$FINALIZER_JOB_ID -o "%.18i %.24j %.10T %.10M %.10l %R"
EOF
