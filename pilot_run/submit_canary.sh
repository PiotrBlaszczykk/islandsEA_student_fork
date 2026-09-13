#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PROJECT_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)
VENV_DIR="${ISLANDS_VENV_DIR:-${HOME}/venvs/islands-ray}"
source "$PROJECT_DIR/hpc_benchmarks/ares_storage.sh"
islandsea_configure_storage
ARTIFACT_ROOT="$ISLANDS_ARTIFACT_ROOT"

module load python/3.10.4-gcccore-11.3.0

[[ "${CONFIRM_TORUS_200:-0}" == "1" ]] || {
    echo "Submission blocked: confirm the proposed 10x20 torus with CONFIRM_TORUS_200=1" >&2
    exit 2
}
[[ -x "$VENV_DIR/bin/python" ]] || { echo "Missing project venv: $VENV_DIR" >&2; exit 2; }

cd "$PROJECT_DIR"
[[ -z "$(git status --porcelain --untracked-files=all)" ]] || {
    echo "Refusing a non-reproducible canary: commit or remove all local changes first." >&2
    git status --short >&2
    exit 2
}

mkdir -p "$ARTIFACT_ROOT/pilot_canaries"
SUBMISSION=$(sbatch --parsable \
    --output="$ISLANDS_SLURM_LOG_DIR/pilot-canary-%j.out" \
    --error="$ISLANDS_SLURM_LOG_DIR/pilot-canary-%j.err" \
    --export="ALL,ISLANDS_ARTIFACT_ROOT=${ARTIFACT_ROOT},ISLANDS_VENV_DIR=${VENV_DIR}" \
    "$SCRIPT_DIR/run_pilot_canary.sh")
JOB_ID="${SUBMISSION%%;*}"
echo "PILOT_CANARY_JOB_ID=$JOB_ID"
echo "CANARY_ARTIFACT_DIR=$ARTIFACT_ROOT/pilot_canaries/$JOB_ID"
echo "CANARY_SLURM_LOG=$ISLANDS_SLURM_LOG_DIR/pilot-canary-$JOB_ID.out"
echo "Monitor: squeue -j $JOB_ID"
echo "Check: sacct -j $JOB_ID --format=JobID,State,ExitCode,Elapsed,AllocCPUS,CPUTimeRAW,MaxRSS"
