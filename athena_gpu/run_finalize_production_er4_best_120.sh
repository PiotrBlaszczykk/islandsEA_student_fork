#!/usr/bin/env bash
# CPU-only post-array packaging. Submitted from login; never runs GA or CUDA.
set -euo pipefail

[[ "$#" -eq 1 && "$1" =~ ^[0-9]+$ ]] || {
    echo "Usage: $0 ARRAY_JOB_ID" >&2
    exit 2
}
: "${ISLANDS_PROJECT_DIR:?absolute Athena checkout required}"
: "${ISLANDS_STORAGE_ROOT:?absolute SCRATCH storage root required}"
VENV_DIR="${ISLANDS_VENV_DIR:-${HOME}/venvs/islands-ray}"
[[ -x "$VENV_DIR/bin/python" ]] || { echo "Missing Athena Python venv" >&2; exit 2; }

ARRAY_JOB_ID="$1"
CAMPAIGN_DIR="$ISLANDS_STORAGE_ROOT/campaigns/er4_best_${ARRAY_JOB_ID}"
RESULTS_ROOT="$ISLANDS_STORAGE_ROOT/results/athena_production_er4_best_120"
LOGS_ROOT="$ISLANDS_STORAGE_ROOT/logs/slurm"
[[ -f "$CAMPAIGN_DIR/campaign_plan.json" ]] || {
    echo "Missing campaign plan: $CAMPAIGN_DIR/campaign_plan.json" >&2
    exit 1
}

module load Python/3.10.4
cd "$ISLANDS_PROJECT_DIR"
ACCOUNTING_TEMP="$CAMPAIGN_DIR/.sacct.${SLURM_JOB_ID:-$$}.tmp"
trap 'rm -f -- "$ACCOUNTING_TEMP"' EXIT
sacct -X -n -P -j "$ARRAY_JOB_ID" \
    --format=JobIDRaw,JobID,State,ExitCode > "$ACCOUNTING_TEMP"
mv -f -- "$ACCOUNTING_TEMP" "$CAMPAIGN_DIR/sacct.txt"

"$VENV_DIR/bin/python" "$ISLANDS_PROJECT_DIR/athena_gpu/campaign_er4_best.py" finalize \
    --campaign-dir "$CAMPAIGN_DIR" \
    --array-job-id "$ARRAY_JOB_ID" \
    --results-root "$RESULTS_ROOT" \
    --logs-root "$LOGS_ROOT" \
    --sacct-file "$CAMPAIGN_DIR/sacct.txt"
echo "ATHENA_ER4_BEST_FINALIZATION_OK=1"
