#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PROJECT_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)
SPEC="$SCRIPT_DIR/pilot_spec.json"
VENV_DIR="${ISLANDS_VENV_DIR:-${HOME}/venvs/islands-ray}"
source "$PROJECT_DIR/hpc_benchmarks/ares_storage.sh"
source "$PROJECT_DIR/hpc_benchmarks/ray_cli_preflight.sh"
islandsea_configure_storage
ARTIFACT_ROOT="$ISLANDS_ARTIFACT_ROOT"
MAX_PARALLEL="${PILOT_MAX_PARALLEL:-3}"
CANARY_JOB_ID="${PILOT_CANARY_JOB_ID:-}"
GATE_JOB_ID="${PILOT_GATE_JOB_ID:-}"
ARRAY_JOB_ID=""
FINALIZER_JOB_ID=""

module load python/3.10.4-gcccore-11.3.0

rollback_submission() {
    local status=$?
    trap - EXIT
    if (( status != 0 )); then
        if [[ -n "$FINALIZER_JOB_ID" ]]; then
            echo "Submission audit failed; cancelling finalizer $FINALIZER_JOB_ID" >&2
            scancel "$FINALIZER_JOB_ID" || echo "Warning: could not cancel finalizer $FINALIZER_JOB_ID" >&2
        fi
        if [[ -n "$ARRAY_JOB_ID" ]]; then
            echo "Submission audit failed; cancelling array $ARRAY_JOB_ID" >&2
            scancel "$ARRAY_JOB_ID" || echo "Warning: could not cancel array $ARRAY_JOB_ID" >&2
        fi
    fi
    exit "$status"
}
trap rollback_submission EXIT

[[ "$MAX_PARALLEL" =~ ^[1-3]$ ]] || {
    echo "PILOT_MAX_PARALLEL must be 1, 2 or 3" >&2
    exit 2
}
[[ "$CANARY_JOB_ID" =~ ^[0-9]+$ ]] || {
    echo "Submission blocked: set PILOT_CANARY_JOB_ID to the completed canary job id." >&2
    exit 2
}
[[ -z "$GATE_JOB_ID" || "$GATE_JOB_ID" =~ ^[0-9]+$ ]] || {
    echo "Submission blocked: PILOT_GATE_JOB_ID must be numeric when set." >&2
    exit 2
}
[[ -f "$SPEC" && -x "$VENV_DIR/bin/python" ]] || {
    echo "Missing pilot spec or project venv: $VENV_DIR" >&2
    exit 2
}

cd "$PROJECT_DIR"
[[ "$(git branch --show-current)" == "summer_benchmarks_ares" ]] || { echo "Use the Ares CPU checkout for this submitter." >&2; exit 2; }
export ISLANDS_PROJECT_DIR="$PROJECT_DIR"
[[ -z "$(git status --porcelain --untracked-files=all)" ]] || {
    echo "Refusing a non-reproducible submission: commit or remove all local changes first." >&2
    git status --short >&2
    exit 2
}
GIT_COMMIT=$(git rev-parse HEAD)

islandsea_validate_ray_cli "$VENV_DIR"
ARRAY_DEPENDENCY_OPTIONS=()
FINALIZER_DEPENDENCY=""
if [[ -n "$GATE_JOB_ID" ]]; then
    # launch_pilot.sh runs on the login node and pre-submits the expensive jobs.
    # The array is released only when the lightweight gate validates the canary.
    ARRAY_DEPENDENCY_OPTIONS+=(--dependency="afterok:${GATE_JOB_ID}" --kill-on-invalid-dep=yes)
    FINALIZER_DEPENDENCY="afterok:${GATE_JOB_ID},afterany:ARRAY_JOB_ID"
else
    "$VENV_DIR/bin/python" "$SCRIPT_DIR/pilot_tools.py" verify-canary \
        --artifact-root "$ARTIFACT_ROOT" \
        --job-id "$CANARY_JOB_ID"
fi

mkdir -p "$ARTIFACT_ROOT"
ARRAY_SUBMISSION=$(sbatch --parsable \
    "${ARRAY_DEPENDENCY_OPTIONS[@]}" \
    --array="1-3%${MAX_PARALLEL}" \
    --output="$ISLANDS_SLURM_LOG_DIR/pilot-%A_%a.out" \
    --error="$ISLANDS_SLURM_LOG_DIR/pilot-%A_%a.err" \
    --export="ALL,ISLANDS_PROJECT_DIR=${PROJECT_DIR},ISLANDS_ARTIFACT_ROOT=${ARTIFACT_ROOT},ISLANDS_VENV_DIR=${VENV_DIR}" \
    "$SCRIPT_DIR/run_pilot_array.sh")
ARRAY_JOB_ID="${ARRAY_SUBMISSION%%;*}"
if [[ -n "$FINALIZER_DEPENDENCY" ]]; then
    FINALIZER_DEPENDENCY="${FINALIZER_DEPENDENCY/ARRAY_JOB_ID/$ARRAY_JOB_ID}"
else
    FINALIZER_DEPENDENCY="afterany:${ARRAY_JOB_ID}"
fi
FINALIZER_SUBMISSION=$(sbatch --parsable \
    --dependency="$FINALIZER_DEPENDENCY" \
    ${GATE_JOB_ID:+--kill-on-invalid-dep=yes} \
    --output="$ISLANDS_SLURM_LOG_DIR/pilot-finalize-%j.out" \
    --error="$ISLANDS_SLURM_LOG_DIR/pilot-finalize-%j.err" \
    --export="ALL,ISLANDS_PROJECT_DIR=${PROJECT_DIR},ISLANDS_ARTIFACT_ROOT=${ARTIFACT_ROOT},ISLANDS_VENV_DIR=${VENV_DIR}" \
    "$SCRIPT_DIR/finalize_pilot.sh" "$ARRAY_JOB_ID")
FINALIZER_JOB_ID="${FINALIZER_SUBMISSION%%;*}"

"$VENV_DIR/bin/python" "$SCRIPT_DIR/pilot_tools.py" record-submission \
    --artifact-root "$ARTIFACT_ROOT" \
    --array-job-id "$ARRAY_JOB_ID" \
    --finalizer-job-id "$FINALIZER_JOB_ID" \
    --canary-job-id "$CANARY_JOB_ID" \
    --max-parallel "$MAX_PARALLEL"
trap - EXIT

echo "PILOT_ARRAY_JOB_ID=$ARRAY_JOB_ID"
echo "PILOT_FINALIZER_JOB_ID=$FINALIZER_JOB_ID"
[[ -z "$GATE_JOB_ID" ]] || echo "PILOT_GATE_JOB_ID=$GATE_JOB_ID"
echo "PILOT_ARTIFACT_DIR=$ARTIFACT_ROOT/$ARRAY_JOB_ID"
echo "PILOT_SLURM_LOG_DIR=$ISLANDS_SLURM_LOG_DIR"
echo "Monitor: squeue -j $ARRAY_JOB_ID,$FINALIZER_JOB_ID"
echo "After completion: sacct -j $ARRAY_JOB_ID,$FINALIZER_JOB_ID --format=JobID,JobName,State,ExitCode,Elapsed,AllocCPUS,CPUTimeRAW,MaxRSS"
