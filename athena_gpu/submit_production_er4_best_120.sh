#!/usr/bin/env bash
# Submit all 40 refined benchmarks x three repeats, ER4/best/plain, D=200.
# One manual SLURM array; no canary, commit gate, retry or follow-up submission.
set -euo pipefail

[[ "$#" -eq 0 ]] || { echo "Usage: $0" >&2; exit 2; }
[[ -z "${SLURM_JOB_ID:-}" ]] || {
    echo "Submit from an Athena login node, not inside an allocation" >&2
    exit 2
}
command -v sbatch >/dev/null || { echo "sbatch is unavailable" >&2; exit 2; }
: "${SCRATCH:?SCRATCH is required}"

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PROJECT_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)
VENV_DIR="${ISLANDS_VENV_DIR:-${HOME}/venvs/islands-ray}"
[[ -x "$VENV_DIR/bin/python" ]] || { echo "Missing Athena venv: $VENV_DIR" >&2; exit 2; }

cd "$PROJECT_DIR"
module load Python/3.10.4
"$VENV_DIR/bin/python" "$SCRIPT_DIR/production_er4_best.py" --check
LOCAL_COMMIT=$(git rev-parse HEAD)

STORAGE_ROOT="${ISLANDS_STORAGE_ROOT:-$SCRATCH/islandsEA}"
RESULT_ROOT="$STORAGE_ROOT/results/athena_production_er4_best_120"
LOG_ROOT="${ISLANDS_SLURM_LOG_DIR:-$STORAGE_ROOT/logs/slurm}"
CAMPAIGN_ROOT="$STORAGE_ROOT/campaigns"
SCRATCH_REAL=$(realpath -m -- "$SCRATCH")
for path in "$STORAGE_ROOT" "$RESULT_ROOT" "$LOG_ROOT" "$CAMPAIGN_ROOT"; do
    case "$(realpath -m -- "$path")/" in
        "$SCRATCH_REAL"/*) ;;
        *) echo "Output path must remain below SCRATCH: $path" >&2; exit 2 ;;
    esac
done

mkdir -p "$RESULT_ROOT" "$LOG_ROOT" "$CAMPAIGN_ROOT"
# Prevent stale interactive-session gates and mode variables from crossing
# sbatch --export=ALL. The production task map is sourced only from array ID.
unset ATHENA_EXPECTED_COMMIT ATHENA_STUDY_CANARY_JOB_ID ATHENA_STUDY_REPEAT ATHENA_FROZEN_ARRAY
# Keep the shared per-run contract at $ISLANDS_STORAGE_ROOT/exports even if an
# old login session exported a one-off bundle destination.
unset ISLANDS_EXPORT_ROOT
SUBMISSION=$(sbatch --parsable \
    --array=1-120%3 \
    --job-name=islandsea-athena-er4-best-120 \
    --nodes=1 \
    --ntasks=1 \
    --cpus-per-task=16 \
    --mem=128000M \
    --time=02:00:00 \
    --partition=plgrid-gpu-a100 \
    --account=plgintobl-gpu-a100 \
    --gres=gpu:1 \
    --output="$LOG_ROOT/athena-er4-best-120-%A_%a.out" \
    --error="$LOG_ROOT/athena-er4-best-120-%A_%a.err" \
    --export="ALL,ISLANDS_PROJECT_DIR=${PROJECT_DIR},ISLANDS_VENV_DIR=${VENV_DIR},ATHENA_STUDY_MODE=full,ATHENA_STUDY_RESULT_ROOT=${RESULT_ROOT},ATHENA_PRODUCTION_ER4_BEST=1" \
    "$SCRIPT_DIR/run_study_job.sh")
ARRAY_JOB_ID="${SUBMISSION%%;*}"
[[ "$ARRAY_JOB_ID" =~ ^[0-9]+$ ]] || { echo "Invalid sbatch response: $SUBMISSION" >&2; exit 1; }
CAMPAIGN_DIR="$CAMPAIGN_ROOT/er4_best_${ARRAY_JOB_ID}"
if ! "$VENV_DIR/bin/python" "$SCRIPT_DIR/campaign_er4_best.py" plan \
    --campaign-dir "$CAMPAIGN_DIR" \
    --array-job-id "$ARRAY_JOB_ID" \
    --git-commit "$LOCAL_COMMIT"; then
    # Without an immutable task plan, do not let the submitted production
    # array consume GPU hours with unindexable results.
    scancel "$ARRAY_JOB_ID" || true
    echo "Campaign plan failed; array $ARRAY_JOB_ID cancellation requested" >&2
    exit 1
fi

echo "ATHENA_ER4_BEST_ARRAY_JOB_ID=$ARRAY_JOB_ID"
echo "ATHENA_ER4_BEST_CONFIGURATIONS=40x3=120"
echo "ATHENA_ER4_BEST_DIMENSION=200"
echo "ATHENA_ER4_BEST_BASE_SEED=20260912"
echo "ATHENA_ER4_BEST_COMMIT=$LOCAL_COMMIT"
echo "ATHENA_ER4_BEST_RESULT_ROOT=$RESULT_ROOT"
echo "ATHENA_ER4_BEST_CAMPAIGN_DIR=$CAMPAIGN_DIR"
echo "ATHENA_ER4_BEST_STDOUT_PATTERN=$LOG_ROOT/athena-er4-best-120-${ARRAY_JOB_ID}_<task>.out"
echo "ATHENA_ER4_BEST_STDERR_PATTERN=$LOG_ROOT/athena-er4-best-120-${ARRAY_JOB_ID}_<task>.err"
echo "ATHENA_ER4_BEST_BUNDLE_PATTERN=$STORAGE_ROOT/exports/run_<element_SLURM_JOB_ID>.tar.gz"
echo "MAX_GPU_HOURS_PER_TASK=2.0"
echo "MAX_TOTAL_GPU_HOURS=240.0"
echo "No automatic retry, resubmission, or follow-up job"
echo "Monitor: squeue -j $ARRAY_JOB_ID"
echo "Accounting: sacct -j $ARRAY_JOB_ID -P --format=JobIDRaw,ArrayJobID,ArrayTaskID,State,ExitCode,Elapsed,AllocCPUS,AllocTRES,MaxRSS,NodeList"
