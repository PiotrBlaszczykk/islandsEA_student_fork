#!/usr/bin/env bash
# Manual login-node submitter. It never submits a follow-up job automatically.
set -euo pipefail

MODE=""
CONFIRM=""
case "${1:-}" in
    --canary)
        MODE=canary
        shift
        ;;
    --full)
        MODE=full
        shift
        CONFIRM="${1:-}"
        [[ "$CONFIRM" == --confirm-one-of-1800-max-2-gpuh ]] || {
            echo "Full run requires --confirm-one-of-1800-max-2-gpuh" >&2
            exit 2
        }
        shift
        ;;
    *)
        echo "Usage: $0 --canary | --full --confirm-one-of-1800-max-2-gpuh" >&2
        exit 2
        ;;
esac
[[ "$#" -eq 0 ]] || { echo "Unexpected arguments" >&2; exit 2; }

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PROJECT_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)
VENV_DIR="${ISLANDS_VENV_DIR:-${HOME}/venvs/islands-ray}"

[[ -z "${SLURM_JOB_ID:-}" ]] || {
    echo "Run this submitter on an Athena login node, not inside an allocation" >&2
    exit 2
}
command -v sbatch >/dev/null || { echo "sbatch is unavailable" >&2; exit 2; }
[[ -n "${SCRATCH:-}" ]] || { echo "SCRATCH is required" >&2; exit 2; }
[[ -x "$VENV_DIR/bin/python" ]] || { echo "Missing Athena venv: $VENV_DIR" >&2; exit 2; }

cd "$PROJECT_DIR"
[[ "$(git branch --show-current)" == summer_benchmarks_athena ]] || {
    echo "Expected branch summer_benchmarks_athena" >&2
    exit 2
}
[[ -z "$(git status --porcelain --untracked-files=all)" ]] || {
    echo "Submission blocked: Git working tree is not clean" >&2
    git status --short >&2
    exit 2
}
LOCAL_COMMIT=$(git rev-parse HEAD)
UPSTREAM_COMMIT=$(git rev-parse '@{upstream}' 2>/dev/null) || {
    echo "Submission blocked: branch has no upstream" >&2
    exit 2
}
[[ "$LOCAL_COMMIT" == "$UPSTREAM_COMMIT" ]] || {
    echo "Submission blocked: HEAD differs from the locally known upstream" >&2
    echo "Run git pull --ff-only origin summer_benchmarks_athena" >&2
    exit 2
}

STORAGE_ROOT="${ISLANDS_STORAGE_ROOT:-$SCRATCH/islandsEA}"
case "$(realpath -m -- "$STORAGE_ROOT")/" in
    "$(realpath -m -- "$SCRATCH")"/*) ;;
    *) echo "ISLANDS_STORAGE_ROOT must remain below SCRATCH" >&2; exit 2 ;;
esac
LOG_ROOT="${ISLANDS_SLURM_LOG_DIR:-$STORAGE_ROOT/logs/slurm}"
if [[ "$MODE" == canary ]]; then
    RESULT_ROOT="${ATHENA_STUDY_CANARY_ROOT:-$STORAGE_ROOT/results/athena_study_canaries}"
    WALLTIME=00:15:00
    JOB_NAME=islandsea-athena-study-canary
    MAX_GPU_HOURS=0.25
else
    RESULT_ROOT="${ATHENA_STUDY_RUN_ROOT:-$STORAGE_ROOT/results/athena_study_runs}"
    WALLTIME=02:00:00
    JOB_NAME=islandsea-athena-study-full
    MAX_GPU_HOURS=2.0
    : "${ATHENA_STUDY_CANARY_JOB_ID:?Set ATHENA_STUDY_CANARY_JOB_ID to a passed canary from this commit}"
    [[ "$ATHENA_STUDY_CANARY_JOB_ID" =~ ^[0-9]+$ ]] || {
        echo "Invalid ATHENA_STUDY_CANARY_JOB_ID" >&2
        exit 2
    }
    CANARY_VALIDATION="${ATHENA_STUDY_CANARY_ROOT:-$STORAGE_ROOT/results/athena_study_canaries}/$ATHENA_STUDY_CANARY_JOB_ID/validation.json"
    [[ -f "$CANARY_VALIDATION" ]] || {
        echo "Missing canary validation: $CANARY_VALIDATION" >&2
        exit 2
    }
    module load Python/3.10.4
    "$VENV_DIR/bin/python" - "$CANARY_VALIDATION" "$LOCAL_COMMIT" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as source:
    value = json.load(source)
if value.get("valid") is not True or value.get("status") != "passed":
    raise SystemExit("Canary validation did not pass")
if value.get("mode") != "canary":
    raise SystemExit("Validation is not an Athena study canary")
if value.get("git_commit") != sys.argv[2]:
    raise SystemExit("Canary commit differs from the full-run commit")
PY
fi

SCRATCH_REAL=$(realpath -m -- "$SCRATCH")
for path in "$RESULT_ROOT" "$LOG_ROOT"; do
    case "$(realpath -m -- "$path")/" in
        "$SCRATCH_REAL"/*) ;;
        *) echo "Result/log path must remain below SCRATCH: $path" >&2; exit 2 ;;
    esac
done
mkdir -p "$RESULT_ROOT" "$LOG_ROOT"

SUBMISSION=$(sbatch --parsable \
    --job-name="$JOB_NAME" \
    --nodes=1 \
    --ntasks=1 \
    --cpus-per-task=16 \
    --mem=128000M \
    --time="$WALLTIME" \
    --partition=plgrid-gpu-a100 \
    --account=plgintobl-gpu-a100 \
    --gres=gpu:1 \
    --output="$LOG_ROOT/athena-study-${MODE}-%j.out" \
    --error="$LOG_ROOT/athena-study-${MODE}-%j.err" \
    --export="ALL,ISLANDS_PROJECT_DIR=${PROJECT_DIR},ISLANDS_VENV_DIR=${VENV_DIR},ATHENA_EXPECTED_COMMIT=${LOCAL_COMMIT},ATHENA_STUDY_MODE=${MODE},ATHENA_STUDY_RESULT_ROOT=${RESULT_ROOT}" \
    "$SCRIPT_DIR/run_study_job.sh")
JOB_ID="${SUBMISSION%%;*}"
[[ "$JOB_ID" =~ ^[0-9]+$ ]] || { echo "Invalid sbatch response: $SUBMISSION" >&2; exit 1; }

echo "ATHENA_STUDY_JOB_ID=$JOB_ID"
echo "ATHENA_STUDY_MODE=$MODE"
echo "ATHENA_STUDY_RESULT=$RESULT_ROOT/$JOB_ID"
echo "ATHENA_STUDY_VALIDATION=$RESULT_ROOT/$JOB_ID/validation.json"
echo "ATHENA_STUDY_STDOUT=$LOG_ROOT/athena-study-${MODE}-$JOB_ID.out"
echo "ATHENA_STUDY_STDERR=$LOG_ROOT/athena-study-${MODE}-$JOB_ID.err"
echo "MAX_GPU_HOURS=$MAX_GPU_HOURS"
echo "No automatic retry and no automatic full-run submission"
echo "Monitor: squeue -j $JOB_ID"
echo "Accounting: sacct -j $JOB_ID -P --format=JobIDRaw,JobName,State,ExitCode,Elapsed,AllocCPUS,AllocTRES,TotalCPU,MaxRSS,NodeList"
