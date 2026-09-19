#!/usr/bin/env bash
# Manual Athena submission of the frozen three-repeat F1/torus/best baseline.
# This script submits exactly one SLURM array (three independent A100 tasks).
set -euo pipefail

[[ "$#" -eq 0 ]] || {
    echo "Usage: $0" >&2
    exit 2
}

# Do not let gates from an earlier interactive session leak through
# sbatch --export=ALL into this deliberately unpinned frozen run.
unset ATHENA_EXPECTED_COMMIT ATHENA_STUDY_CANARY_JOB_ID

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
LOCAL_COMMIT=$(git rev-parse HEAD 2>/dev/null || printf 'unknown')

STORAGE_ROOT="${ISLANDS_STORAGE_ROOT:-$SCRATCH/islandsEA}"
SCRATCH_REAL=$(realpath -m -- "$SCRATCH")
case "$(realpath -m -- "$STORAGE_ROOT")/" in
    "$SCRATCH_REAL"/*) ;;
    *) echo "ISLANDS_STORAGE_ROOT must remain below SCRATCH" >&2; exit 2 ;;
esac
RESULT_ROOT="${ATHENA_FROZEN_RUN_ROOT:-$STORAGE_ROOT/results/athena_frozen_torus3}"
LOG_ROOT="${ISLANDS_SLURM_LOG_DIR:-$STORAGE_ROOT/logs/slurm}"
for path in "$RESULT_ROOT" "$LOG_ROOT"; do
    case "$(realpath -m -- "$path")/" in
        "$SCRATCH_REAL"/*) ;;
        *) echo "Result/log path must remain below SCRATCH: $path" >&2; exit 2 ;;
    esac
done

module load Python/3.10.4
"$VENV_DIR/bin/python" - "$PROJECT_DIR/pilot_run/pilot_spec.json" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as source:
    spec = json.load(source)
expected = {
    "benchmark": "r01_elliptic",
    "benchmark_family": "continuous",
    "dimension": 200,
    "islands": 144,
    "evaluations_per_island": 8000,
    "population": 16,
    "offspring": 4,
    "migrants": 5,
    "migration_interval": 5,
    "topology": "torus",
    "torus_rows": 12,
    "torus_columns": 12,
    "migrant_selection": "best",
    "migrant_acceptance": "plain",
    "base_seed": 20260912,
    "repeats": [1, 2, 3],
    "metrics_profile": "research-v1-full-buffered",
}
for key, value in expected.items():
    if spec.get(key) != value:
        raise SystemExit(f"Frozen cross-platform spec mismatch for {key}: {spec.get(key)!r}")
PY

mkdir -p "$RESULT_ROOT" "$LOG_ROOT"
SUBMISSION=$(sbatch --parsable \
    --array=1-3%3 \
    --job-name=islandsea-athena-frozen-torus3 \
    --nodes=1 \
    --ntasks=1 \
    --cpus-per-task=16 \
    --mem=128000M \
    --time=02:00:00 \
    --partition=plgrid-gpu-a100 \
    --account=plgintobl-gpu-a100 \
    --gres=gpu:1 \
    --output="$LOG_ROOT/athena-frozen-torus3-%A_%a.out" \
    --error="$LOG_ROOT/athena-frozen-torus3-%A_%a.err" \
    --export="ALL,ISLANDS_PROJECT_DIR=${PROJECT_DIR},ISLANDS_VENV_DIR=${VENV_DIR},ATHENA_STUDY_MODE=full,ATHENA_STUDY_RESULT_ROOT=${RESULT_ROOT},ATHENA_FROZEN_ARRAY=1" \
    "$SCRIPT_DIR/run_study_job.sh")
ARRAY_JOB_ID="${SUBMISSION%%;*}"
[[ "$ARRAY_JOB_ID" =~ ^[0-9]+$ ]] || {
    echo "Invalid sbatch response: $SUBMISSION" >&2
    exit 1
}

echo "ATHENA_FROZEN_ARRAY_JOB_ID=$ARRAY_JOB_ID"
echo "ATHENA_FROZEN_REPEATS=1,2,3"
echo "ATHENA_FROZEN_BASE_SEED=20260912"
echo "ATHENA_FROZEN_COMMIT=$LOCAL_COMMIT"
echo "ATHENA_FROZEN_RESULT_ROOT=$RESULT_ROOT"
echo "ATHENA_FROZEN_STDOUT_PATTERN=$LOG_ROOT/athena-frozen-torus3-${ARRAY_JOB_ID}_<repeat>.out"
echo "ATHENA_FROZEN_STDERR_PATTERN=$LOG_ROOT/athena-frozen-torus3-${ARRAY_JOB_ID}_<repeat>.err"
echo "ATHENA_FROZEN_BUNDLE_PATTERN=$STORAGE_ROOT/exports/run_<element_SLURM_JOB_ID>.tar.gz"
echo "MAX_GPU_HOURS_PER_REPEAT=2.0"
echo "MAX_TOTAL_GPU_HOURS=6.0"
echo "No automatic retry, resubmission, or follow-up job"
echo "Monitor: squeue -j $ARRAY_JOB_ID"
echo "Accounting: sacct -j $ARRAY_JOB_ID -P --format=JobIDRaw,JobName,State,ExitCode,Elapsed,ElapsedRaw,AllocCPUS,AllocTRES,TotalCPU,MaxRSS,NodeList"
