#!/usr/bin/env bash

set -euo pipefail
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PROJECT_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)
source "$PROJECT_DIR/hpc_benchmarks/ares_storage.sh"
islandsea_configure_storage

SUBMISSION=$(sbatch --parsable \
    --output="$ISLANDS_SLURM_LOG_DIR/smoke-%j.out" \
    --error="$ISLANDS_SLURM_LOG_DIR/smoke-%j.err" \
    --export=ALL \
    "$SCRIPT_DIR/run_smoke.sh")
JOB_ID="${SUBMISSION%%;*}"
echo "JOB_ID=$JOB_ID"
echo "SLURM_LOG=$ISLANDS_SLURM_LOG_DIR/smoke-$JOB_ID.out"
