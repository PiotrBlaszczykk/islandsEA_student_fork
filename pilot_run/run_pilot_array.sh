#!/usr/bin/env bash
#SBATCH --job-name=island-pilot
#SBATCH --nodes=9
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=48
#SBATCH --mem-per-cpu=2G
#SBATCH --time=00:30:00
#SBATCH --partition=plgrid
#SBATCH --account=plglscclass26-cpu
#SBATCH --output=/tmp/island-pilot-%A_%a.out
#SBATCH --error=/tmp/island-pilot-%A_%a.err

set -euo pipefail
: "${SLURM_ARRAY_JOB_ID:?Submit through pilot_run/submit_pilot.sh}"
: "${SLURM_ARRAY_TASK_ID:?Missing SLURM_ARRAY_TASK_ID}"
: "${PILOT_EXPECTED_COMMIT:?Missing pinned pilot commit}"

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PROJECT_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)
VENV_DIR="${ISLANDS_VENV_DIR:-${HOME}/venvs/islands-ray}"
source "$PROJECT_DIR/hpc_benchmarks/ares_storage.sh"
islandsea_configure_storage
ARTIFACT_ROOT="$ISLANDS_ARTIFACT_ROOT"
REPEAT="$SLURM_ARRAY_TASK_ID"
RUN_ARTIFACT_DIR="$ARTIFACT_ROOT/$SLURM_ARRAY_JOB_ID/repeat-$REPEAT"
ATTEMPT="$RUN_ARTIFACT_DIR/attempt.json"
RESULT_POINTER="$RUN_ARTIFACT_DIR/result_pointer.json"

mkdir -p "$RUN_ARTIFACT_DIR"
module load python/3.10.4-gcccore-11.3.0
source "$VENV_DIR/bin/activate"
cd "$PROJECT_DIR"
ACTUAL_COMMIT=$(git rev-parse HEAD)
[[ "$ACTUAL_COMMIT" == "$PILOT_EXPECTED_COMMIT" ]] || {
    echo "Pilot blocked: expected commit $PILOT_EXPECTED_COMMIT, found $ACTUAL_COMMIT." >&2
    exit 2
}
[[ -z "$(git status --porcelain --untracked-files=all)" ]] || {
    echo "Pilot blocked: checkout became dirty after submission." >&2
    git status --short >&2
    exit 2
}

"$VENV_DIR/bin/python" "$SCRIPT_DIR/pilot_tools.py" record-attempt \
    --path "$ATTEMPT" --status running --repeat "$REPEAT"

finish_attempt() {
    local status=$?
    trap - EXIT
    set +e
    if (( status == 0 )); then
        "$VENV_DIR/bin/python" "$SCRIPT_DIR/pilot_tools.py" record-attempt \
            --path "$ATTEMPT" --status completed --repeat "$REPEAT" --exit-code 0
    else
        "$VENV_DIR/bin/python" "$SCRIPT_DIR/pilot_tools.py" record-attempt \
            --path "$ATTEMPT" --status failed --repeat "$REPEAT" --exit-code "$status"
    fi
    exit "$status"
}
trap finish_attempt EXIT

mapfile -t BENCHMARK_ARGS < <(
    "$VENV_DIR/bin/python" "$SCRIPT_DIR/pilot_tools.py" benchmark-args --repeat "$REPEAT"
)
[[ "${#BENCHMARK_ARGS[@]}" -gt 0 ]] || {
    echo "Pilot configuration produced no benchmark arguments" >&2
    exit 2
}

export ISLANDS_PROJECT_DIR="$PROJECT_DIR"
export ISLANDS_VENV_DIR="$VENV_DIR"
export ISLANDS_RAY_FAILURE_DIR="$ISLANDS_RAY_FAILURE_ROOT/pilot-$SLURM_ARRAY_JOB_ID/repeat-$REPEAT"
export ISLANDS_EFFECT_HORIZON_STEPS=25
islandsea_print_storage
cd "$PROJECT_DIR"
bash "$PROJECT_DIR/hpc_benchmarks/run_ares.sh" \
    "${BENCHMARK_ARGS[@]}" \
    --result-pointer "$RESULT_POINTER"
