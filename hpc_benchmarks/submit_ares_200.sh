#!/usr/bin/env bash

# Submit the fixed 200-island Ares resource profile with SCRATCH-backed logs.
set -euo pipefail
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PROJECT_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)
source "$SCRIPT_DIR/ares_storage.sh"
islandsea_configure_storage
export ISLANDS_PROJECT_DIR="${ISLANDS_PROJECT_DIR:-$PROJECT_DIR}"
SBATCH_OPTIONS=()
if [[ -n "${ISLANDS_WALLTIME:-}" ]]; then
    SBATCH_OPTIONS+=(--time="$ISLANDS_WALLTIME")
fi

SUBMISSION=$(sbatch --parsable \
    "${SBATCH_OPTIONS[@]}" \
    --output="$ISLANDS_SLURM_LOG_DIR/benchmark-200-%j.out" \
    --error="$ISLANDS_SLURM_LOG_DIR/benchmark-200-%j.err" \
    --export=ALL \
    "$SCRIPT_DIR/run_ares_200.sh" "$@")
JOB_ID="${SUBMISSION%%;*}"
echo "JOB_ID=$JOB_ID"
echo "SLURM_LOG=$ISLANDS_SLURM_LOG_DIR/benchmark-200-$JOB_ID.out"
echo "RESULTS_ROOT=$ISLANDS_RUN_OUTPUT_ROOT"
