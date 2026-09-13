#!/usr/bin/env bash
#SBATCH --job-name=island-pilot-canary
#SBATCH --nodes=9
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=48
#SBATCH --mem-per-cpu=2G
#SBATCH --time=00:10:00
#SBATCH --partition=plgrid
#SBATCH --account=plglscclass26-cpu
#SBATCH --output=/tmp/island-pilot-canary-%j.out
#SBATCH --error=/tmp/island-pilot-canary-%j.err

set -euo pipefail
: "${SLURM_JOB_ID:?Submit through pilot_run/submit_canary.sh}"

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PROJECT_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)
source "$PROJECT_DIR/hpc_benchmarks/ares_storage.sh"
islandsea_configure_storage
ARTIFACT_ROOT="$ISLANDS_ARTIFACT_ROOT"
CANARY_DIR="$ARTIFACT_ROOT/pilot_canaries/$SLURM_JOB_ID"

mkdir -p "$CANARY_DIR"
export ISLANDS_PROJECT_DIR="$PROJECT_DIR"
export ISLANDS_RAY_FAILURE_DIR="$ISLANDS_RAY_FAILURE_ROOT/pilot-canary-$SLURM_JOB_ID"
export ISLANDS_EFFECT_HORIZON_STEPS=25
islandsea_print_storage
cd "$PROJECT_DIR"
bash "$PROJECT_DIR/hpc_benchmarks/run_ares.sh" \
    --problem r01_elliptic \
    --dimension 200 \
    --islands 200 \
    --evaluations 128 \
    --population 16 \
    --offspring 4 \
    --migrants 5 \
    --interval 5 \
    --topology torus \
    --torus-rows 10 \
    --torus-columns 20 \
    --strategy best \
    --acceptance plain \
    --repeat 1 \
    --seed 20260912 \
    --startup-timeout 300 \
    --actor-startup-timeout 300 \
    --result-pointer "$CANARY_DIR/result_pointer.json"
