#!/bin/bash
#SBATCH --job-name=islands-smoke
#SBATCH --nodes=2
#SBATCH --ntasks=32
#SBATCH --time=0:20:00
#SBATCH --mem-per-cpu=4GB
#SBATCH -p plgrid
#SBATCH -A plglscclass26-cpu

set -euo pipefail

if [[ -z "${SLURM_JOB_ID:-}" ]]; then
  echo "Ten skrypt uruchamiaj przez sbatch (nie przez sh)."
  echo "Uzyj: sbatch run_smoke_ring.sh"
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
echo "Logowanie i tunel SSH: ssh -N -L 18265:${head_node}:${dashboard_port} ${USER}@login01.ares.cyfronet.pl"

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

number_of_islands=12
number_of_migrants=2
migration_interval=20
dda=$(date +%y%m%d)
tta=$(date +%H%M%S)
topolog="ring"      # ring | torus | complete | er1 | er2 | er3 | er4 | ws3 | ws4
strateg="random"    # random | best | worst | maxDistance
strateg2="BEZ"      # tekst zawierajacy "SAS" aktywuje wariant SAS

python3 -u islands_desync/start.py \
  "$number_of_islands" "$tmpdir" \
  "$number_of_migrants" "$migration_interval" \
  "$dda" "$tta" "$topolog" "$strateg" "$strateg2"

keep_dashboard_seconds="${KEEP_DASHBOARD_SECONDS:-0}"
if [[ "$keep_dashboard_seconds" -gt 0 ]]; then
  echo "Trzymam job jeszcze ${keep_dashboard_seconds}s dla dashboardu..."
  sleep "$keep_dashboard_seconds"
fi
