#!/usr/bin/env bash
# One short, isolated BA/best diagnostic on the production Ares CPU profile.
set -euo pipefail
[[ -z "${SLURM_JOB_ID:-}" ]] || { echo "Run on the login node" >&2; exit 2; }
: "${SCRATCH:?SCRATCH must be available on Ares}"
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PROJECT_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd -P)
VENV_DIR="${ISLANDS_VENV_DIR:-${HOME}/venvs/islands-ray}"
SMOKE_DIR="$SCRATCH/ba_smoke"

[[ ! -e "$SMOKE_DIR" ]] || { echo "Refusing to overwrite $SMOKE_DIR" >&2; exit 2; }
[[ -x "$VENV_DIR/bin/python" ]] || { echo "Ares venv is missing" >&2; exit 2; }
[[ -f "$SCRIPT_DIR/run_ba_smoke.sh" && -f "$SCRIPT_DIR/verify_ba_smoke.py" && \
   -f "$PROJECT_DIR/hpc_benchmarks/run_bundle.py" ]] || {
    echo "BA smoke runner, validator or exporter is missing" >&2; exit 2;
}
cd "$PROJECT_DIR"
[[ "$(git branch --show-current)" == "summer_ares_blaszczyk" ]] || {
    echo "Use branch summer_ares_blaszczyk" >&2; exit 2;
}
[[ -z "$(git status --porcelain --untracked-files=all)" ]] || {
    echo "Commit or remove local changes before submission" >&2; exit 2;
}

module load python/3.10.4-gcccore-11.3.0
source "$VENV_DIR/bin/activate"
source "$PROJECT_DIR/hpc_benchmarks/ray_cli_preflight.sh"
islandsea_validate_ray_cli "$VENV_DIR"
ISLANDS_CAMPAIGN_TOPOLOGY=ba ISLANDS_CAMPAIGN_STRATEGY=best \
    "$VENV_DIR/bin/python" -c \
    'import sys; sys.path.insert(0, sys.argv[1]); from campaign_tools import validate_study_graph_source; validate_study_graph_source(); print("BA_GRAPH_SOURCE_OK")' \
    "$SCRIPT_DIR"
"$VENV_DIR/bin/python" "$PROJECT_DIR/hpc_benchmarks/run_benchmark.py" \
    --problem r01_elliptic --dimension 200 --islands 144 --diagnostic \
    --evaluations 128 --population 16 --offspring 4 --migrants 5 --interval 5 \
    --topology ba --strategy best --acceptance plain --repeat 1 --seed 20260912 \
    --startup-timeout 300 --actor-startup-timeout 300 --dry-run
echo "BA_SMOKE_PREFLIGHT_OK islands=144 evaluations=128 topology=ba strategy=best"

mkdir -p "$SMOKE_DIR/logs/slurm"
SUBMISSION=$(sbatch --parsable \
    --job-name=ba-smoke --nodes=7 --ntasks-per-node=1 --cpus-per-task=48 \
    --mem-per-cpu=2G --time=00:10:00 --partition=plgrid \
    --account=plglscclass26-cpu \
    --output="$SMOKE_DIR/logs/slurm/ba-smoke-%j.out" \
    --error="$SMOKE_DIR/logs/slurm/ba-smoke-%j.err" \
    --export="ALL,ISLANDS_PROJECT_DIR=${PROJECT_DIR},ISLANDS_VENV_DIR=${VENV_DIR},ISLANDS_BA_SMOKE_DIR=${SMOKE_DIR}" \
    "$SCRIPT_DIR/run_ba_smoke.sh")
JOB_ID="${SUBMISSION%%;*}"
[[ "$JOB_ID" =~ ^[0-9]+$ ]] || { echo "Invalid sbatch response: $SUBMISSION" >&2; exit 1; }
echo "BA_SMOKE_JOB_ID=$JOB_ID"
echo "BA_SMOKE_DIR=$SMOKE_DIR"
echo "BA_SMOKE_CPUH_CEILING=56"
echo "Monitor: squeue -j $JOB_ID -o '%.18i %.24j %.10T %.10M %.10l %R'"
echo "After completion: bash main_runs/check_ba_smoke.sh $JOB_ID"
