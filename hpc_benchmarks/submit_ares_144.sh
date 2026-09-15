#!/usr/bin/env bash

# Submit the fixed 144-island Ares resource profile with SCRATCH-backed logs.
set -euo pipefail
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PROJECT_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)
[[ "$(git -C "$PROJECT_DIR" branch --show-current)" == "summer_benchmarks_ares" ]] || { echo "Use the Ares CPU checkout for this submitter." >&2; exit 2; }
source "$SCRIPT_DIR/ares_storage.sh"
islandsea_configure_storage
export ISLANDS_PROJECT_DIR="${ISLANDS_PROJECT_DIR:-$PROJECT_DIR}"
SBATCH_OPTIONS=()
if [[ -n "${ISLANDS_WALLTIME:-}" ]]; then
    SBATCH_OPTIONS+=(--time="$ISLANDS_WALLTIME")
fi

module load python/3.10.4-gcccore-11.3.0
VENV_DIR="${ISLANDS_VENV_DIR:-${HOME}/venvs/islands-ray}"
"$VENV_DIR/bin/python" "$PROJECT_DIR/hpc_benchmarks/run_benchmark.py" "$@" --islands 144 --dry-run

SUBMISSION=$(sbatch --parsable \
    "${SBATCH_OPTIONS[@]}" \
    --output="$ISLANDS_SLURM_LOG_DIR/benchmark-144-%j.out" \
    --error="$ISLANDS_SLURM_LOG_DIR/benchmark-144-%j.err" \
    --export=ALL \
    "$SCRIPT_DIR/run_ares_144.sh" "$@")
JOB_ID="${SUBMISSION%%;*}"
echo "JOB_ID=$JOB_ID"
echo "SLURM_LOG=$ISLANDS_SLURM_LOG_DIR/benchmark-144-$JOB_ID.out"
echo "RESULTS_ROOT=$ISLANDS_RUN_OUTPUT_ROOT"
