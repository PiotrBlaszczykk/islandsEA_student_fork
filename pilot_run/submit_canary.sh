#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PROJECT_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)
VENV_DIR="${ISLANDS_VENV_DIR:-${HOME}/venvs/islands-ray}"
source "$PROJECT_DIR/hpc_benchmarks/ares_storage.sh"
islandsea_configure_storage
ARTIFACT_ROOT="$ISLANDS_ARTIFACT_ROOT"

module load python/3.10.4-gcccore-11.3.0

[[ -x "$VENV_DIR/bin/python" ]] || { echo "Missing project venv: $VENV_DIR" >&2; exit 2; }

cd "$PROJECT_DIR"
[[ "$(git branch --show-current)" == "summer_benchmarks_ares" ]] || { echo "Use the Ares CPU checkout for this submitter." >&2; exit 2; }
export ISLANDS_PROJECT_DIR="$PROJECT_DIR"
"$VENV_DIR/bin/python" -m unittest pilot_run.test_spool_paths
[[ -z "$(git status --porcelain --untracked-files=all)" ]] || {
    echo "Refusing a non-reproducible canary: commit or remove all local changes first." >&2
    git status --short >&2
    exit 2
}
GIT_COMMIT=$(git rev-parse HEAD)
if [[ -n "${PILOT_EXPECTED_COMMIT:-}" && "$GIT_COMMIT" != "$PILOT_EXPECTED_COMMIT" ]]; then
    echo "Submission blocked: expected commit $PILOT_EXPECTED_COMMIT, found $GIT_COMMIT." >&2
    exit 2
fi

mapfile -t CANARY_ARGS < <(
    "$VENV_DIR/bin/python" "$SCRIPT_DIR/pilot_tools.py" benchmark-args --repeat 1
)
[[ "${#CANARY_ARGS[@]}" -gt 0 ]] || {
    echo "Pilot configuration produced no canary arguments." >&2
    exit 2
}
PLAN_JSON=$("$VENV_DIR/bin/python" "$PROJECT_DIR/hpc_benchmarks/run_benchmark.py" \
    "${CANARY_ARGS[@]}" --evaluations 128 --dry-run)
printf '%s\n' "$PLAN_JSON"
"$VENV_DIR/bin/python" -c '
import json, sys
p = json.loads(sys.argv[1])
expected = {
    "islands": 144,
    "dimension": 200,
    "evaluations": 128,
    "required_ray_cpus": 289,
    "required_slurm_cpus": 290,
    "topology": "torus",
    "strategy": "best",
    "acceptance": "plain",
}
bad = {key: (p.get(key), value) for key, value in expected.items() if p.get(key) != value}
if bad:
    raise SystemExit(f"Invalid canary dry-run plan: {bad}")
print("PILOT_CANARY_DRY_RUN_OK")
' "$PLAN_JSON"

mkdir -p "$ARTIFACT_ROOT/pilot_canaries"
SUBMISSION=$(sbatch --parsable \
    --output="$ISLANDS_SLURM_LOG_DIR/pilot-canary-%j.out" \
    --error="$ISLANDS_SLURM_LOG_DIR/pilot-canary-%j.err" \
    --export="ALL,ISLANDS_PROJECT_DIR=${PROJECT_DIR},ISLANDS_ARTIFACT_ROOT=${ARTIFACT_ROOT},ISLANDS_VENV_DIR=${VENV_DIR},PILOT_EXPECTED_COMMIT=${GIT_COMMIT}" \
    "$SCRIPT_DIR/run_pilot_canary.sh")
JOB_ID="${SUBMISSION%%;*}"
echo "PILOT_CANARY_JOB_ID=$JOB_ID"
echo "CANARY_ARTIFACT_DIR=$ARTIFACT_ROOT/pilot_canaries/$JOB_ID"
echo "CANARY_SLURM_LOG=$ISLANDS_SLURM_LOG_DIR/pilot-canary-$JOB_ID.out"
echo "Monitor: squeue -j $JOB_ID"
echo "Check: sacct -j $JOB_ID --format=JobID,State,ExitCode,Elapsed,AllocCPUS,CPUTimeRAW,MaxRSS"
