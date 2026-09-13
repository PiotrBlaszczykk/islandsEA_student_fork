#!/usr/bin/env bash
# Ares resource profile for the current 200-island actor architecture.
# 200 Island + 200 Computation + 1 SignalActor = 401 Ray CPUs. The generic
# launcher advertises 431 Ray CPUs from this 9x48 allocation and keeps one
# additional physical CPU on the head node for the driver.
#SBATCH --job-name=islandsea-200
#SBATCH --nodes=9
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=48
#SBATCH --mem-per-cpu=2G
#SBATCH --time=00:30:00
#SBATCH --partition=plgrid
#SBATCH --account=plglscclass26-cpu
#SBATCH --output=/tmp/islandsea-200-%j.out
#SBATCH --error=/tmp/islandsea-200-%j.err

set -euo pipefail
: "${SLURM_JOB_ID:?Submit this script with sbatch from the repository root}"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

# Put fixed safety-critical values last so an accidental duplicate CLI option
# cannot silently turn this profile into a differently sized experiment.
exec bash "$SCRIPT_DIR/run_ares.sh" "$@" --islands 200 --startup-timeout 300
