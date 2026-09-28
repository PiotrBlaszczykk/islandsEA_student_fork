#!/usr/bin/env bash
# Submit from Athena login; requires an explicitly authorized CPU-only resource.
set -euo pipefail

[[ "$#" -eq 2 && ( "$1" == --afterany || "$1" == --existing ) && "$2" =~ ^[0-9]+$ ]] || {
    echo "Usage: $0 --afterany|--existing ARRAY_JOB_ID" >&2
    exit 2
}
[[ -z "${SLURM_JOB_ID:-}" ]] || { echo "Submit from a login node" >&2; exit 2; }
: "${SCRATCH:?SCRATCH is required}"
: "${ATHENA_FINALIZER_PARTITION:?Set the authorized CPU-only partition; Athena A100 is GPU-only}"
: "${ATHENA_FINALIZER_ACCOUNT:?Set the authorized CPU-only account}"
[[ "$ATHENA_FINALIZER_PARTITION" != *gpu* && "$ATHENA_FINALIZER_ACCOUNT" != *gpu* ]] || {
    echo "Refusing a GPU resource for CPU-only finalization" >&2
    exit 2
}
command -v sbatch >/dev/null || { echo "sbatch is unavailable" >&2; exit 2; }

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PROJECT_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd -P)
STORAGE_ROOT="${ISLANDS_STORAGE_ROOT:-$SCRATCH/islandsEA}"
VENV_DIR="${ISLANDS_VENV_DIR:-${HOME}/venvs/islands-ray}"
[[ -x "$VENV_DIR/bin/python" ]] || { echo "Missing Athena venv: $VENV_DIR" >&2; exit 2; }
SCRATCH_REAL=$(realpath -m -- "$SCRATCH")
case "$(realpath -m -- "$STORAGE_ROOT")/" in
    "$SCRATCH_REAL"/*) ;;
    *) echo "Storage must remain below SCRATCH" >&2; exit 2 ;;
esac

ARRAY_JOB_ID="$2"
CAMPAIGN_DIR="$STORAGE_ROOT/campaigns/er4_best_${ARRAY_JOB_ID}"
[[ -f "$CAMPAIGN_DIR/campaign_plan.json" ]] || {
    echo "Missing campaign plan: $CAMPAIGN_DIR/campaign_plan.json" >&2
    exit 2
}
mkdir -p "$CAMPAIGN_DIR/logs"
DEPENDENCY=()
if [[ "$1" == --afterany ]]; then
    DEPENDENCY=("--dependency=afterany:${ARRAY_JOB_ID}")
fi

SUBMISSION=$(sbatch --parsable \
    --job-name=athena-er4-best-finalize \
    "${DEPENDENCY[@]}" \
    --nodes=1 --ntasks=1 --cpus-per-task=1 --mem=16G --time=12:00:00 \
    --partition="$ATHENA_FINALIZER_PARTITION" \
    --account="$ATHENA_FINALIZER_ACCOUNT" \
    --output="$CAMPAIGN_DIR/logs/athena-er4-best-finalize-%j.out" \
    --error="$CAMPAIGN_DIR/logs/athena-er4-best-finalize-%j.err" \
    --export="ALL,ISLANDS_PROJECT_DIR=${PROJECT_DIR},ISLANDS_STORAGE_ROOT=${STORAGE_ROOT},ISLANDS_VENV_DIR=${VENV_DIR}" \
    "$SCRIPT_DIR/run_finalize_production_er4_best_120.sh" "$ARRAY_JOB_ID")
FINALIZER_JOB_ID="${SUBMISSION%%;*}"
[[ "$FINALIZER_JOB_ID" =~ ^[0-9]+$ ]] || { echo "Invalid sbatch response: $SUBMISSION" >&2; exit 1; }
echo "ATHENA_ER4_BEST_FINALIZER_JOB_ID=$FINALIZER_JOB_ID"
echo "ATHENA_ER4_BEST_FINALIZER_DEPENDENCY=${DEPENDENCY[*]:-none; already completed array}"
echo "ATHENA_ER4_BEST_FINALIZER_ARCHIVE=$CAMPAIGN_DIR/er4_best_${ARRAY_JOB_ID}.tar.gz"
