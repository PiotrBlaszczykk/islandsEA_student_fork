#!/usr/bin/env bash

# Submit the fixed torus/best campaign: 40 benchmarks x 3 independent repeats.
# This file runs on the login node. All sbatch calls deliberately happen here.
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PROJECT_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd -P)
VENV_DIR="${ISLANDS_VENV_DIR:-${HOME}/venvs/islands-ray}"
MAX_PARALLEL="${TORUS_BEST_MAX_PARALLEL:-3}"
: "${SCRATCH:?SCRATCH must be available on Ares}"
CAMPAIGN_DIR="${TORUS_BEST_CAMPAIGN_DIR:-$SCRATCH/torus_best}"
TOOLS="$SCRIPT_DIR/campaign_tools.py"
PLAN="$CAMPAIGN_DIR/campaign_plan.json"
ARRAY_JOB_ID=""
FINALIZER_JOB_ID=""

[[ "$MAX_PARALLEL" =~ ^[1-3]$ ]] || {
    echo "TORUS_BEST_MAX_PARALLEL must be 1, 2 or 3" >&2
    exit 2
}
case "$CAMPAIGN_DIR" in
    "$SCRATCH"/*) ;;
    *) echo "Campaign directory must be an absolute child of SCRATCH: $CAMPAIGN_DIR" >&2; exit 2 ;;
esac
[[ ! -e "$CAMPAIGN_DIR" ]] || {
    echo "Refusing to overwrite an existing campaign: $CAMPAIGN_DIR" >&2
    exit 2
}
[[ -x "$VENV_DIR/bin/python" && -f "$TOOLS" ]] || {
    echo "Missing campaign tools or Ares venv: $VENV_DIR" >&2
    exit 2
}

cd "$PROJECT_DIR"
[[ "$(git branch --show-current)" == "summer_ares_blaszczyk" ]] || {
    echo "Use branch summer_ares_blaszczyk on Ares" >&2
    exit 2
}
[[ -z "$(git status --porcelain --untracked-files=all)" ]] || {
    echo "Refusing a non-reproducible submission: commit or remove local changes first" >&2
    git status --short >&2
    exit 2
}
GIT_COMMIT=$(git rev-parse HEAD)

module load python/3.10.4-gcccore-11.3.0
source "$VENV_DIR/bin/activate"
source "$PROJECT_DIR/hpc_benchmarks/ray_cli_preflight.sh"
islandsea_validate_ray_cli "$VENV_DIR"

# A full campaign temporarily keeps raw data, portable run directories,
# individual archives and the final aggregate. Refuse an obviously undersized
# filesystem before submitting 120 expensive jobs.
AVAILABLE_KIB=$(df -Pk "$SCRATCH" | awk 'NR==2 {print $4}')
MINIMUM_KIB=$((150 * 1024 * 1024))
[[ "$AVAILABLE_KIB" =~ ^[0-9]+$ && "$AVAILABLE_KIB" -ge "$MINIMUM_KIB" ]] || {
    echo "At least 150 GiB free on the SCRATCH filesystem is required" >&2
    exit 2
}

# Validate all forty exact problem/dimension combinations without starting Ray.
mapfile -t BENCHMARKS < <("$VENV_DIR/bin/python" -c \
    'import sys; sys.path.insert(0, sys.argv[1]); from campaign_tools import BENCHMARKS; print("\n".join(BENCHMARKS))' \
    "$SCRIPT_DIR")
[[ "${#BENCHMARKS[@]}" -eq 40 ]] || { echo "Expected exactly 40 benchmarks" >&2; exit 2; }
for benchmark in "${BENCHMARKS[@]}"; do
    "$VENV_DIR/bin/python" "$PROJECT_DIR/hpc_benchmarks/run_benchmark.py" \
        --problem "$benchmark" --dimension 200 --islands 144 \
        --evaluations 8000 --population 16 --offspring 4 \
        --migrants 5 --interval 5 --topology torus \
        --torus-rows 12 --torus-columns 12 \
        --strategy best --acceptance plain --repeat 1 --seed 20260912 \
        --startup-timeout 300 --actor-startup-timeout 300 --dry-run >/dev/null
done
echo "TORUS_BEST_PREFLIGHT_OK benchmarks=40 tasks=120"

mkdir -p "$CAMPAIGN_DIR/logs" "$CAMPAIGN_DIR/tasks" "$CAMPAIGN_DIR/runs"
"$VENV_DIR/bin/python" "$TOOLS" create-plan --output "$PLAN" --git-commit "$GIT_COMMIT"

rollback_submission() {
    local status=$?
    trap - EXIT
    if (( status != 0 )); then
        [[ -z "$FINALIZER_JOB_ID" ]] || scancel "$FINALIZER_JOB_ID" || true
        [[ -z "$ARRAY_JOB_ID" ]] || scancel "$ARRAY_JOB_ID" || true
    fi
    exit "$status"
}
trap rollback_submission EXIT

ARRAY_SUBMISSION=$(sbatch --parsable \
    --array="1-120%${MAX_PARALLEL}" \
    --output="$CAMPAIGN_DIR/logs/torus-best-%A_%a.out" \
    --error="$CAMPAIGN_DIR/logs/torus-best-%A_%a.err" \
    --export="ALL,ISLANDS_PROJECT_DIR=${PROJECT_DIR},ISLANDS_CAMPAIGN_DIR=${CAMPAIGN_DIR},ISLANDS_VENV_DIR=${VENV_DIR}" \
    "$SCRIPT_DIR/run_torus_best_array.sh")
ARRAY_JOB_ID="${ARRAY_SUBMISSION%%;*}"

FINALIZER_SUBMISSION=$(sbatch --parsable \
    --dependency="afterany:${ARRAY_JOB_ID}" \
    --output="$CAMPAIGN_DIR/logs/torus-best-finalize-%j.out" \
    --error="$CAMPAIGN_DIR/logs/torus-best-finalize-%j.err" \
    --export="ALL,ISLANDS_PROJECT_DIR=${PROJECT_DIR},ISLANDS_CAMPAIGN_DIR=${CAMPAIGN_DIR},ISLANDS_VENV_DIR=${VENV_DIR}" \
    "$SCRIPT_DIR/finalize_torus_best.sh" "$ARRAY_JOB_ID")
FINALIZER_JOB_ID="${FINALIZER_SUBMISSION%%;*}"

"$VENV_DIR/bin/python" "$TOOLS" record-submission \
    --plan "$PLAN" --output "$CAMPAIGN_DIR/submission.json" \
    --array-job-id "$ARRAY_JOB_ID" --finalizer-job-id "$FINALIZER_JOB_ID" \
    --max-parallel "$MAX_PARALLEL"
trap - EXIT

cat <<EOF
TORUS_BEST_ARRAY_JOB_ID=$ARRAY_JOB_ID
TORUS_BEST_FINALIZER_JOB_ID=$FINALIZER_JOB_ID
TORUS_BEST_CAMPAIGN_DIR=$CAMPAIGN_DIR
TORUS_BEST_EXPECTED_RUNS=120
TORUS_BEST_MAX_PARALLEL=$MAX_PARALLEL
TORUS_BEST_ALLOCATION_CEILING_CPUH=40320
Monitor: squeue -j $ARRAY_JOB_ID,$FINALIZER_JOB_ID -o "%.18i %.24j %.10T %.10M %.10l %R"
Accounting: sacct -X -j $ARRAY_JOB_ID,$FINALIZER_JOB_ID --format=JobID,JobName,State,ExitCode,Elapsed,AllocCPUS,CPUTimeRAW,MaxRSS
Final archive: $CAMPAIGN_DIR/torus_best.tar.gz
EOF
