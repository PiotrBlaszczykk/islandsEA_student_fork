#!/usr/bin/env bash

# Submit the generic Ares benchmark while placing persistent SLURM output in
# SCRATCH. Arguments are forwarded to run_ares.sh as benchmark arguments.
set -euo pipefail
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PROJECT_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)
[[ "$(git -C "$PROJECT_DIR" branch --show-current)" == "summer_benchmarks_ares" ]] || { echo "Use the Ares CPU checkout for this submitter." >&2; exit 2; }
source "$SCRIPT_DIR/ares_storage.sh"
islandsea_configure_storage
export ISLANDS_PROJECT_DIR="${ISLANDS_PROJECT_DIR:-$PROJECT_DIR}"

module load python/3.10.4-gcccore-11.3.0
VENV_DIR="${ISLANDS_VENV_DIR:-${HOME}/venvs/islands-ray}"
PLAN_JSON=$("$VENV_DIR/bin/python" "$PROJECT_DIR/hpc_benchmarks/run_benchmark.py" "$@" --dry-run)
printf '%s\n' "$PLAN_JSON"
# Keep explicitly requested one/two-island diagnostics inexpensive.
ISLAND_COUNT=$("$VENV_DIR/bin/python" -c 'import json, sys; print(json.loads(sys.argv[1])["islands"])' "$PLAN_JSON")
SBATCH_OPTIONS=()
if (( ISLAND_COUNT <= 2 )); then
    SBATCH_OPTIONS+=(--nodes=1 --cpus-per-task=6)
fi

SUBMISSION=$(sbatch --parsable \
    "${SBATCH_OPTIONS[@]}" \
    --output="$ISLANDS_SLURM_LOG_DIR/benchmark-%j.out" \
    --error="$ISLANDS_SLURM_LOG_DIR/benchmark-%j.err" \
    --export=ALL \
    "$SCRIPT_DIR/run_ares.sh" "$@")
JOB_ID="${SUBMISSION%%;*}"
echo "JOB_ID=$JOB_ID"
echo "SLURM_LOG=$ISLANDS_SLURM_LOG_DIR/benchmark-$JOB_ID.out"
echo "RESULTS_ROOT=$ISLANDS_RUN_OUTPUT_ROOT"
