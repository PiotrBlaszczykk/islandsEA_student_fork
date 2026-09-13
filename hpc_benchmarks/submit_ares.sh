#!/usr/bin/env bash

# Submit the generic Ares benchmark while placing persistent SLURM output in
# SCRATCH. Arguments are forwarded to run_ares.sh as benchmark arguments.
set -euo pipefail
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PROJECT_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)
source "$SCRIPT_DIR/ares_storage.sh"
islandsea_configure_storage
export ISLANDS_PROJECT_DIR="${ISLANDS_PROJECT_DIR:-$PROJECT_DIR}"

SUBMISSION=$(sbatch --parsable \
    --output="$ISLANDS_SLURM_LOG_DIR/benchmark-%j.out" \
    --error="$ISLANDS_SLURM_LOG_DIR/benchmark-%j.err" \
    --export=ALL \
    "$SCRIPT_DIR/run_ares.sh" "$@")
JOB_ID="${SUBMISSION%%;*}"
echo "JOB_ID=$JOB_ID"
echo "SLURM_LOG=$ISLANDS_SLURM_LOG_DIR/benchmark-$JOB_ID.out"
echo "RESULTS_ROOT=$ISLANDS_RUN_OUTPUT_ROOT"
