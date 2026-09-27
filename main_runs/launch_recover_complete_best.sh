#!/usr/bin/env bash
# Recover the 120 scientifically validated Complete/best runs without Ray.
# Run only on the Ares login node after committing the exporter fix.
set -euo pipefail
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PROJECT_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd -P)
VENV_DIR="${ISLANDS_VENV_DIR:-${HOME}/venvs/islands-ray}"
: "${SCRATCH:?SCRATCH must be available on Ares}"
CAMPAIGN_DIR="$SCRATCH/complete_best"
MAX_PARALLEL="${COMPLETE_BEST_RECOVERY_MAX_PARALLEL:-3}"
[[ "$MAX_PARALLEL" =~ ^[1-3]$ ]] || {
    echo "COMPLETE_BEST_RECOVERY_MAX_PARALLEL must be 1, 2 or 3" >&2
    exit 2
}
[[ -f "$CAMPAIGN_DIR/submission.json" && ! -e "$CAMPAIGN_DIR/complete_best.tar.gz" ]] || {
    echo "Existing, unfinalized Complete/best campaign is required" >&2
    exit 2
}

cd "$PROJECT_DIR"
[[ "$(git branch --show-current)" == "summer_ares_blaszczyk" ]] || {
    echo "Use branch summer_ares_blaszczyk on Ares" >&2
    exit 2
}
[[ -z "$(git status --porcelain --untracked-files=all)" ]] || {
    echo "Commit or remove local changes before recovery" >&2
    exit 2
}
[[ -x "$VENV_DIR/bin/python" ]] || { echo "Ares venv is missing" >&2; exit 2; }

module load python/3.10.4-gcccore-11.3.0
source "$VENV_DIR/bin/activate"
export ISLANDS_CAMPAIGN_TOPOLOGY=complete
export ISLANDS_CAMPAIGN_STRATEGY=best
"$VENV_DIR/bin/python" "$SCRIPT_DIR/recover_complete_best.py" preflight \
    --campaign-dir "$CAMPAIGN_DIR"

ORIGINAL_ARRAY_JOB_ID=$("$VENV_DIR/bin/python" -c \
    'import json,sys; print(json.load(open(sys.argv[1]))["array_job_id"])' \
    "$CAMPAIGN_DIR/submission.json")
[[ "$ORIGINAL_ARRAY_JOB_ID" == 21111388 ]] || {
    echo "Expected the affected Complete/best array 21111388" >&2
    exit 2
}

SUBMISSION_LOCK="$CAMPAIGN_DIR/.recovery_submission_lock"
mkdir "$SUBMISSION_LOCK" || {
    echo "Recovery has already been submitted or is being submitted" >&2
    exit 2
}
RECOVERY_ARRAY_JOB_ID=""
FINALIZER_JOB_ID=""
rollback_submission() {
    local status=$?
    trap - EXIT
    if (( status != 0 )); then
        [[ -z "$FINALIZER_JOB_ID" ]] || scancel "$FINALIZER_JOB_ID" || true
        [[ -z "$RECOVERY_ARRAY_JOB_ID" ]] || scancel "$RECOVERY_ARRAY_JOB_ID" || true
        rmdir "$SUBMISSION_LOCK" || true
    fi
    exit "$status"
}
trap rollback_submission EXIT

RECOVERY_SUBMISSION=$(sbatch --parsable \
    --array="1-120%${MAX_PARALLEL}" \
    --output="$CAMPAIGN_DIR/logs/complete-best-recover-%A_%a.out" \
    --error="$CAMPAIGN_DIR/logs/complete-best-recover-%A_%a.err" \
    --export="ALL,ISLANDS_PROJECT_DIR=${PROJECT_DIR},ISLANDS_CAMPAIGN_DIR=${CAMPAIGN_DIR},ISLANDS_VENV_DIR=${VENV_DIR}" \
    "$SCRIPT_DIR/recover_complete_best_array.sh")
RECOVERY_ARRAY_JOB_ID="${RECOVERY_SUBMISSION%%;*}"

FINALIZER_SUBMISSION=$(sbatch --parsable \
    --job-name=complete-best-finalize \
    --dependency="afterany:${RECOVERY_ARRAY_JOB_ID}" \
    --output="$CAMPAIGN_DIR/logs/complete-best-finalize-%j.out" \
    --error="$CAMPAIGN_DIR/logs/complete-best-finalize-%j.err" \
    --export="ALL,ISLANDS_PROJECT_DIR=${PROJECT_DIR},ISLANDS_CAMPAIGN_DIR=${CAMPAIGN_DIR},ISLANDS_VENV_DIR=${VENV_DIR},ISLANDS_CAMPAIGN_TOPOLOGY=complete,ISLANDS_CAMPAIGN_STRATEGY=best" \
    "$SCRIPT_DIR/finalize_torus_best.sh" "$ORIGINAL_ARRAY_JOB_ID" "$RECOVERY_ARRAY_JOB_ID")
FINALIZER_JOB_ID="${FINALIZER_SUBMISSION%%;*}"
"$VENV_DIR/bin/python" -c '
import json, pathlib, sys
path = pathlib.Path(sys.argv[1])
path.write_text(json.dumps({"original_array_job_id": sys.argv[2],
    "recovery_array_job_id": sys.argv[3], "finalizer_job_id": sys.argv[4]}, indent=2) + "\n")
' "$CAMPAIGN_DIR/recovery_submission.json" "$ORIGINAL_ARRAY_JOB_ID" "$RECOVERY_ARRAY_JOB_ID" "$FINALIZER_JOB_ID"
trap - EXIT

cat <<EOF
COMPLETE_BEST_RECOVERY_ARRAY_JOB_ID=$RECOVERY_ARRAY_JOB_ID
COMPLETE_BEST_RECOVERY_FINALIZER_JOB_ID=$FINALIZER_JOB_ID
COMPLETE_BEST_ORIGINAL_ARRAY_JOB_ID=$ORIGINAL_ARRAY_JOB_ID
Monitor: squeue -j $RECOVERY_ARRAY_JOB_ID,$FINALIZER_JOB_ID -o "%.18i %.24j %.10T %.10M %.10l %R"
Accounting: sacct -n -X -P -j $RECOVERY_ARRAY_JOB_ID,$FINALIZER_JOB_ID --format=State,ExitCode | sort | uniq -c
EOF
