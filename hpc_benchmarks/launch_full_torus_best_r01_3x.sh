#!/usr/bin/env bash

# Production entry point for one study configuration (three repetitions).
# The implementation deliberately delegates to the validated pilot pipeline so
# the canary, commit pinning, SLURM resource profile, validation, accounting and
# portable run bundles cannot drift from the configuration that already passed
# on Ares.
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PROJECT_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)
CONFIRMATION="${1:-}"

if [[ "$#" -ne 1 || "$CONFIRMATION" != "--confirm-144-and-562-cpuh" ]]; then
    cat >&2 <<'EOF'
Usage: bash hpc_benchmarks/launch_full_torus_best_r01_3x.sh --confirm-144-and-562-cpuh

Submits one fixed study configuration on Ares:
  benchmark: r01_elliptic (continuous), dimension 200
  topology: torus 12x12, 144 islands
  migration: best selection, plain acceptance, 5 migrants every 5 evaluations
  algorithm: population 16, offspring 4, 8000 evaluations per island
  repetitions: 1, 2, 3 (distinct deterministic seed bases)

The command first submits a 128-evaluation canary for the current clean commit.
Only a strictly valid canary lets the gate submit the three full repetitions
and their finalizer. The rounded allocation ceiling is 562 CPUh; there are no
automatic retries.
EOF
    exit 2
fi

cat <<EOF
=== FIXED FULL-RUN CONFIGURATION ===
benchmark=r01_elliptic
benchmark_family=continuous
dimension=200
topology=torus
torus_shape=12x12
islands=144
migrant_selection=best
migrant_acceptance=plain
migrants=5
migration_interval=5
population=16
offspring=4
evaluations_per_island=8000
repeats=1,2,3
base_seed=20260912
max_parallel_repeats=${PILOT_MAX_PARALLEL:-3}
portable_exports=\$SCRATCH/islandsEA/exports/run_<SLURM_JOB_ID>.tar.gz
EOF

exec bash "$PROJECT_DIR/pilot_run/launch_pilot.sh" "$CONFIRMATION"
