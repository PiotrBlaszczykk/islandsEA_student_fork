#!/usr/bin/env bash
# Ares resource profile for the current 144-island actor architecture.
# 144 Island + 144 Computation + 1 SignalActor = 289 Ray CPUs. The generic
# launcher advertises 335 Ray CPUs from this 7x48 allocation and keeps one
# additional physical CPU on the head node for the driver.
#SBATCH --job-name=islandsea-144
#SBATCH --nodes=7
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=48
#SBATCH --mem-per-cpu=2G
#SBATCH --time=00:30:00
#SBATCH --partition=plgrid
#SBATCH --account=plglscclass26-cpu
#SBATCH --output=/tmp/islandsea-144-%j.out
#SBATCH --error=/tmp/islandsea-144-%j.err

set -euo pipefail
: "${SLURM_JOB_ID:?Submit this script with sbatch from the repository root}"
PROJECT_DIR="${ISLANDS_PROJECT_DIR:-${SLURM_SUBMIT_DIR:?Missing submission directory}}"
SCRIPT_DIR="$PROJECT_DIR/hpc_benchmarks"

# Put fixed safety-critical values last so an accidental duplicate CLI option
# cannot silently turn this profile into a differently sized experiment.
exec bash "$SCRIPT_DIR/run_ares.sh" "$@" --islands 144 --startup-timeout 300
