#!/bin/bash
# Submits delay experiment jobs for different topologies and strategies.
#
# What this submits (27 jobs total):
#   144 islands: ring, torus, complete
#   Strategy: plain, newer, dup_newer, stochastic, window:10, oldest
#   Repetitions: 3

set -euo pipefail

SLEEP_SECONDS=60
SCRIPT="${SCRIPT:-run_delay_experiment.sh}"

STRATEGIES=("plain" "newer" "dup_newer" "stochastic" "window:10" "oldest")
REPS=(1 2 3)

TOPOLOGIES_144=("ring" "torus" "complete")

submitted=0

echo "=== Submitting 144-island topologies ==="

for rep in "${REPS[@]}"; do
  for topo in "${TOPOLOGIES_144[@]}"; do
    for strat in "${STRATEGIES[@]}"; do

      echo "Submitting: islands=144 topology=$topo strategy=$strat rep=$rep"

      sbatch \
        --export=ALL,NUMBER_OF_ISLANDS=144,TOPOLOGY="$topo",ACCEPTANCE_STRATEGY="$strat",REPETITION="$rep" \
        "$SCRIPT"

      submitted=$((submitted + 1))

      sleep "$SLEEP_SECONDS"

    done
  done
done

echo ""
echo "=== Submitted $submitted jobs total ==="
echo "Monitor with: squeue -u \$USER"
