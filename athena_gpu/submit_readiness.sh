#!/usr/bin/env bash

# Login-node submitter for the one-A100 readiness canary.
set -euo pipefail
MODE=f1
case "${1:-}" in
    "") ;;
    --suite) MODE=suite; shift ;;
    *) echo "Usage: $0 [--suite]" >&2; exit 2 ;;
esac
[[ "$#" -eq 0 ]] || { echo "Unexpected arguments" >&2; exit 2; }

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PROJECT_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)
VENV_DIR="${ISLANDS_VENV_DIR:-${HOME}/venvs/islands-ray}"

[[ -z "${SLURM_JOB_ID:-}" ]] || {
    echo "Run this submitter on an Athena login node, not inside an allocation." >&2
    exit 2
}
command -v sbatch >/dev/null || { echo "sbatch is unavailable." >&2; exit 2; }
[[ -n "${SCRATCH:-}" ]] || { echo "SCRATCH is required; refusing HOME fallback." >&2; exit 2; }
[[ -x "$VENV_DIR/bin/python" ]] || { echo "Missing Athena venv: $VENV_DIR" >&2; exit 2; }

cd "$PROJECT_DIR"
[[ "$(git branch --show-current)" == "summer_benchmarks_athena" ]] || {
    echo "Expected branch summer_benchmarks_athena." >&2
    exit 2
}
[[ -z "$(git status --porcelain --untracked-files=all)" ]] || {
    echo "Submission blocked: Git working tree is not clean." >&2
    git status --short >&2
    exit 2
}
LOCAL_COMMIT=$(git rev-parse HEAD)
UPSTREAM_COMMIT=$(git rev-parse '@{upstream}' 2>/dev/null) || {
    echo "Submission blocked: branch has no upstream." >&2
    exit 2
}
[[ "$LOCAL_COMMIT" == "$UPSTREAM_COMMIT" ]] || {
    echo "Submission blocked: HEAD differs from the locally known upstream." >&2
    echo "Run git pull --ff-only origin summer_benchmarks_athena." >&2
    exit 2
}

STORAGE_ROOT="${ISLANDS_STORAGE_ROOT:-$SCRATCH/islandsEA}"
case "$STORAGE_ROOT/" in
    "$SCRATCH"/*) ;;
    *)
        echo "ISLANDS_STORAGE_ROOT must be below SCRATCH." >&2
        exit 2
        ;;
esac
if [[ "$MODE" == suite ]]; then
    RESULT_ROOT="${ATHENA_BENCHMARK_VALIDATION_ROOT:-$STORAGE_ROOT/results/athena_benchmark_validation}"
    RESULT_FILE=validation.json
else
    RESULT_ROOT="${ATHENA_READINESS_ROOT:-$STORAGE_ROOT/results/athena_gpu_readiness}"
    RESULT_FILE=readiness.json
fi
LOG_ROOT="${ISLANDS_SLURM_LOG_DIR:-$STORAGE_ROOT/logs/slurm}"
SCRATCH_REAL=$(realpath -m -- "$SCRATCH")
for path in "$RESULT_ROOT" "$LOG_ROOT"; do
    case "$(realpath -m -- "$path")/" in
        "$SCRATCH_REAL"/*) ;;
        *) echo "Result/log path must remain below SCRATCH: $path" >&2; exit 2 ;;
    esac
done
mkdir -p "$RESULT_ROOT" "$LOG_ROOT"

SUBMISSION=$(sbatch --parsable \
    --job-name=islandsea-athena-gpu-ready \
    --nodes=1 \
    --ntasks=1 \
    --cpus-per-task=16 \
    --mem=128000M \
    --time=00:15:00 \
    --partition=plgrid-gpu-a100 \
    --account=plgintobl-gpu-a100 \
    --gres=gpu:1 \
    --output="$LOG_ROOT/athena-gpu-readiness-%j.out" \
    --error="$LOG_ROOT/athena-gpu-readiness-%j.err" \
    --export="ALL,ISLANDS_PROJECT_DIR=${PROJECT_DIR},ISLANDS_VENV_DIR=${VENV_DIR},ATHENA_READINESS_ROOT=${RESULT_ROOT},ATHENA_EXPECTED_COMMIT=${LOCAL_COMMIT},ATHENA_VALIDATION_MODE=${MODE}" \
    "$SCRIPT_DIR/run_readiness.sh")
JOB_ID="${SUBMISSION%%;*}"
[[ "$JOB_ID" =~ ^[0-9]+$ ]] || { echo "Invalid sbatch response: $SUBMISSION" >&2; exit 1; }

echo "ATHENA_GPU_READINESS_JOB_ID=$JOB_ID"
echo "ATHENA_VALIDATION_MODE=$MODE"
echo "ATHENA_GPU_READINESS_RESULT=$RESULT_ROOT/$JOB_ID/$RESULT_FILE"
echo "ATHENA_GPU_READINESS_STDOUT=$LOG_ROOT/athena-gpu-readiness-$JOB_ID.out"
echo "ATHENA_GPU_READINESS_STDERR=$LOG_ROOT/athena-gpu-readiness-$JOB_ID.err"
echo "MAX_GPU_HOURS=0.25"
echo "No automatic retry."
echo "Monitor: squeue -j $JOB_ID"
echo "Accounting: sacct -j $JOB_ID -P --format=JobIDRaw,JobName,Account,State,ExitCode,Elapsed,AllocCPUS,AllocTRES,NodeList"
