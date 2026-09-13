#!/usr/bin/env bash

set -euo pipefail
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PROJECT_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)
source "$SCRIPT_DIR/ares_storage.sh"
islandsea_configure_storage
export ISLANDS_PROJECT_DIR="${ISLANDS_PROJECT_DIR:-$PROJECT_DIR}"

SUBMISSION=$(sbatch --parsable \
    --output="$ISLANDS_SLURM_LOG_DIR/validation-%j.out" \
    --error="$ISLANDS_SLURM_LOG_DIR/validation-%j.err" \
    --export=ALL \
    "$SCRIPT_DIR/validate_ares.sh")
JOB_ID="${SUBMISSION%%;*}"
echo "JOB_ID=$JOB_ID"
echo "SLURM_LOG=$ISLANDS_SLURM_LOG_DIR/validation-$JOB_ID.out"
echo "VALIDATION_RESULT=$ISLANDS_RESULTS_ROOT/validation/validation-$JOB_ID.json"
