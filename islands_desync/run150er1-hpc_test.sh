#!/bin/bash
#SBATCH --job-name=islands-150er1-test
#SBATCH --nodes=8
#SBATCH --ntasks=192
#SBATCH --time=02:00:00
#SBATCH --mem-per-cpu=4GB
#SBATCH -p plgrid
#SBATCH -A plglscclass26-cpu

set -euo pipefail

if [[ -z "${SLURM_JOB_ID:-}" ]]; then
  echo "Run with sbatch, not sh."
  echo "Example: sbatch run150er1-hpc_test.sh"
  exit 1
fi

module load python/3.10.4-gcccore-11.3.0
source "$HOME/venvs/islands-ray/bin/activate"

mkdir -p "/tmp/$USER/$SLURM_JOB_ID"
tmpdir="/tmp/$USER/$SLURM_JOB_ID"

export TMPDIR="$tmpdir"
export RAY_TMPDIR="$tmpdir"
export PYTHONPATH="${PYTHONPATH:-}:$PWD"

nodes=$(scontrol show hostnames "$SLURM_JOB_NODELIST")
nodes_array=($nodes)

head_node=${nodes_array[0]}
head_node_ip=$(srun --nodes=1 --ntasks=1 -w "$head_node" hostname --ip-address | awk '{print $1}')

port=6379
dashboard_port=8265
ip_head="${head_node_ip}:${port}"
export ip_head

echo "IP Head: $ip_head"
echo "Dashboard: http://${head_node}:${dashboard_port}"
echo "Tunnel: ssh -N -L 18265:${head_node}:${dashboard_port} ${USER}@login01.ares.cyfronet.pl"

echo "Starting HEAD at $head_node"
srun --nodes=1 --ntasks=1 -w "$head_node" \
  ray start --head --node-ip-address="$head_node_ip" --port="$port" \
  --dashboard-host=0.0.0.0 --dashboard-port="$dashboard_port" \
  --temp-dir="$tmpdir" --block &
sleep 5

worker_num=$((SLURM_JOB_NUM_NODES - 1))
for ((i=1; i<=worker_num; i++)); do
  node_i=${nodes_array[$i]}
  echo "Starting WORKER $i at $node_i"
  srun --nodes=1 --ntasks=1 -w "$node_i" --export=ALL,RAY_TMPDIR="$tmpdir" \
    ray start --address "$ip_head" --block &
  sleep 1
done

run_tag="150er1_test"
number_of_islands="${NUMBER_OF_ISLANDS:-150}"
number_of_migrants="${NUMBER_OF_MIGRANTS:-5}"
migration_interval="${MIGRATION_INTERVAL:-5}"
dda=$(date +%y%m%d)
tta=$(date +%H%M%S)
topolog="er1"
strateg="${MIGRANT_STRATEGY:-random}"
strateg2="${MIGRANT_ACCEPT_STRATEGY:-BEZ}"

python3 -u islands_desync/start.py \
  "$number_of_islands" "$tmpdir" \
  "$number_of_migrants" "$migration_interval" \
  "$dda" "$tta" "$topolog" "$strateg" "$strateg2"

slurm_out="${SLURM_SUBMIT_DIR}/slurm-${SLURM_JOB_ID}.out"
run_dir=""
for _ in $(seq 1 30); do
  if [[ -f "$slurm_out" ]]; then
    run_dir=$(grep "KAT logs/" "$slurm_out" | tail -n1 | sed 's/.*KAT //' | tr -d '\r')
    if [[ -n "$run_dir" ]]; then
      break
    fi
  fi
  sleep 1
done

if [[ -n "$run_dir" && -d "$run_dir" ]]; then
  plots_dir="${SLURM_SUBMIT_DIR}/plot_exports/${dda}/${tta}_${run_tag}"
  mkdir -p "$plots_dir"

  python3 -u plot_all_islands.py "$run_dir" "$plots_dir/fitness_all_islands.png" || true
  cp "$run_dir/___RESULT.txt" "$plots_dir/" 2>/dev/null || true
  cp "$run_dir/___WINNER.txt" "$plots_dir/" 2>/dev/null || true
  cp "$run_dir/param.json" "$plots_dir/" 2>/dev/null || true

  echo "RUN_DIR: $run_dir"
  echo "PLOTS_DIR: $plots_dir"
else
  echo "WARN: could not resolve run directory from $slurm_out"
fi

keep_dashboard_seconds="${KEEP_DASHBOARD_SECONDS:-0}"
if [[ "$keep_dashboard_seconds" -gt 0 ]]; then
  echo "Keeping job alive for dashboard: ${keep_dashboard_seconds}s"
  sleep "$keep_dashboard_seconds"
fi
