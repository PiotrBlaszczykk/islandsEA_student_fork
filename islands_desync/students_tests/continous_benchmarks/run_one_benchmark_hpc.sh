#!/bin/bash
# Generic one-run SLURM wrapper for the Ray/HPC path.
# Submit from the outer islands_desync directory or from any child directory:
#   sbatch students_tests/continous_benchmarks/run_one_benchmark_hpc.sh
# Override values with --export or environment variables.

#SBATCH --job-name=islands-bench
#SBATCH --nodes=2
#SBATCH --ntasks=32
#SBATCH --time=00:40:00
#SBATCH --mem-per-cpu=4GB
#SBATCH -p plgrid
#SBATCH -A plglscclass26-cpu

set -euo pipefail

if [[ -z "${SLURM_JOB_ID:-}" ]]; then
  echo "Run with sbatch, not sh."
  echo "Example: sbatch students_tests/continous_benchmarks/run_one_benchmark_hpc.sh"
  exit 1
fi

submit_dir="${SLURM_SUBMIT_DIR:-$PWD}"
if [[ -f "${submit_dir}/islands_desync/start.py" ]]; then
  islands_root="$submit_dir"
elif [[ -f "${submit_dir}/islands_desync/islands_desync/start.py" ]]; then
  islands_root="${submit_dir}/islands_desync"
else
  echo "Cannot find outer islands_desync runtime directory from SLURM_SUBMIT_DIR=${submit_dir}"
  echo "Submit from the repository root or from the outer islands_desync directory."
  exit 1
fi

script_dir="${islands_root}/students_tests/continous_benchmarks"
cd "$islands_root"

python_module="${PYTHON_MODULE:-python/3.10.4-gcccore-11.3.0}"
if [[ -n "$python_module" && "$python_module" != "none" ]]; then
  module load "$python_module"
else
  echo "Skipping module load; using Python from PATH/venv."
fi
source "${VENV_PATH:-$HOME/venvs/islands-ray/bin/activate}"

mkdir -p "/tmp/$USER/$SLURM_JOB_ID"
tmpdir="/tmp/$USER/$SLURM_JOB_ID"

export TMPDIR="$tmpdir"
export RAY_TMPDIR="$tmpdir"
export PYTHONPATH="${PYTHONPATH:-}:$PWD"
export RAY_DEDUP_LOGS="${RAY_DEDUP_LOGS:-0}"
export RAY_USAGE_STATS_ENABLED="${RAY_USAGE_STATS_ENABLED:-0}"
export RAY_raylet_start_wait_time_s="${RAY_raylet_start_wait_time_s:-300}"

export ISLANDS_PROBLEM="${ISLANDS_PROBLEM:-sphere}"
export ISLANDS_NUMBER_OF_VARIABLES="${ISLANDS_NUMBER_OF_VARIABLES:-30}"
export ISLANDS_NUMBER_OF_EVALUATIONS="${ISLANDS_NUMBER_OF_EVALUATIONS:-600}"
export ISLANDS_POPULATION_SIZE="${ISLANDS_POPULATION_SIZE:-16}"
export ISLANDS_OFFSPRING_POPULATION_SIZE="${ISLANDS_OFFSPRING_POPULATION_SIZE:-4}"

benchmark_name="${BENCHMARK_NAME:-${ISLANDS_PROBLEM}_${TOPOLOGY:-ring}_${NUMBER_OF_ISLANDS:-12}_${MIGRANT_STRATEGY:-random}_r${REPEAT:-1}}"
number_of_islands="${NUMBER_OF_ISLANDS:-12}"
number_of_migrants="${NUMBER_OF_MIGRANTS:-2}"
migration_interval="${MIGRATION_INTERVAL:-20}"
topolog="${TOPOLOGY:-ring}"
strateg="${MIGRANT_STRATEGY:-random}"
strateg2="${MIGRANT_ACCEPT_STRATEGY:-BEZ}"

dda=$(date +%y%m%d)
tta=$(date +%H%M%S)

nodes=$(scontrol show hostnames "$SLURM_JOB_NODELIST")
nodes_array=($nodes)

head_node=${nodes_array[0]}
head_node_ip=$(srun --nodes=1 --ntasks=1 -w "$head_node" hostname --ip-address | awk '{print $1}')

port="${RAY_PORT:-$((20000 + SLURM_JOB_ID % 20000))}"
dashboard_port="${RAY_DASHBOARD_PORT:-$((40000 + SLURM_JOB_ID % 20000))}"
ip_head="${head_node_ip}:${port}"
export ip_head
export RAY_ADDRESS="${RAY_ADDRESS:-$ip_head}"

echo "BENCHMARK_NAME: $benchmark_name"
echo "Problem: ${ISLANDS_PROBLEM}"
echo "Variables: ${ISLANDS_NUMBER_OF_VARIABLES}"
echo "Evaluations: ${ISLANDS_NUMBER_OF_EVALUATIONS}"
echo "Islands/topology: ${number_of_islands}/${topolog}"
echo "Migration: strategy=${strateg}, accept=${strateg2}, migrants=${number_of_migrants}, interval=${migration_interval}"
echo "IP Head: $ip_head"
echo "RAY_ADDRESS: $RAY_ADDRESS"
echo "Dashboard: http://${head_node}:${dashboard_port}"
echo "Tunnel: ssh -N -L 18265:${head_node}:${dashboard_port} ${USER}@login01.ares.cyfronet.pl"
echo "Ray raylet startup wait: ${RAY_raylet_start_wait_time_s}s"

echo "Starting HEAD at $head_node"
srun --nodes=1 --ntasks=1 -w "$head_node" \
  ray start --head --node-ip-address="$head_node_ip" --port="$port" \
  --dashboard-host=0.0.0.0 --dashboard-port="$dashboard_port" \
  --temp-dir="$tmpdir" --block &

head_wait_seconds="${RAY_HEAD_STARTUP_WAIT_SECONDS:-180}"
echo "Waiting up to ${head_wait_seconds}s for Ray head port ${ip_head}"
head_ready=0
for _ in $(seq 1 "$head_wait_seconds"); do
  if python3 -c 'import socket, sys; s=socket.socket(); s.settimeout(1); s.connect((sys.argv[1], int(sys.argv[2]))); s.close()' "$head_node_ip" "$port" >/dev/null 2>&1; then
    head_ready=1
    break
  fi
  sleep 1
done

if [[ "$head_ready" -ne 1 ]]; then
  echo "ERROR: Ray head did not open ${ip_head} within ${head_wait_seconds}s"
  exit 1
fi
echo "Ray head port is reachable."

worker_num=$((SLURM_JOB_NUM_NODES - 1))
for ((i=1; i<=worker_num; i++)); do
  node_i=${nodes_array[$i]}
  echo "Starting WORKER $i at $node_i"
  srun --nodes=1 --ntasks=1 -w "$node_i" --export=ALL,RAY_TMPDIR="$tmpdir" \
    ray start --address "$ip_head" --block &
  sleep "${RAY_WORKER_STARTUP_SPACING_SECONDS:-2}"
done

cluster_wait_seconds="${RAY_CLUSTER_READY_WAIT_SECONDS:-300}"
expected_nodes="${SLURM_JOB_NUM_NODES}"
echo "Waiting up to ${cluster_wait_seconds}s for ${expected_nodes} Ray nodes"
cluster_ready=0
for _ in $(seq 1 "$cluster_wait_seconds"); do
  active_nodes=$(python3 -c 'import ray, sys; ray.init(address=sys.argv[1], logging_level="ERROR"); print(sum(1 for node in ray.nodes() if node.get("Alive"))); ray.shutdown()' "$ip_head" 2>/dev/null || echo 0)
  echo "Ray active nodes: ${active_nodes}/${expected_nodes}"
  if [[ "$active_nodes" -ge "$expected_nodes" ]]; then
    cluster_ready=1
    break
  fi
  sleep 1
done

if [[ "$cluster_ready" -ne 1 ]]; then
  echo "ERROR: Ray cluster did not reach ${expected_nodes} active nodes within ${cluster_wait_seconds}s"
  exit 1
fi
echo "Ray cluster is ready."

python3 -u islands_desync/start.py \
  "$number_of_islands" "$tmpdir" \
  "$number_of_migrants" "$migration_interval" \
  "$dda" "$tta" "$topolog" "$strateg" "$strateg2"

slurm_out="${SLURM_SUBMIT_DIR}/slurm-${SLURM_JOB_ID}.out"
run_dir=""
for _ in $(seq 1 30); do
  if [[ -f "$slurm_out" ]]; then
    run_dir=$(grep "KAT logs/" "$slurm_out" | tail -n1 | sed 's/.*KAT //' | tr -d '\r')
    if [[ -n "$run_dir" && -d "$run_dir" ]]; then
      break
    fi
  fi
  sleep 1
done

if [[ -z "$run_dir" || ! -d "$run_dir" ]]; then
  echo "WARN: could not resolve run directory from $slurm_out"
else
  export_base_dir="${EXPORT_BASE_DIR:-${script_dir}/exports}"
  export_dir="${export_base_dir}/${dda}/${tta}_${benchmark_name}"
  mkdir -p "$export_dir"

  python3 -u plot_all_islands.py "$run_dir" "$export_dir/fitness_all_islands.png" || true
  timeseries_csv="$export_dir/fitness_timeseries.csv"
  if [[ "${COMPRESS_FITNESS_TIMESERIES:-0}" == "1" ]]; then
    timeseries_csv="${timeseries_csv}.gz"
  fi

  python3 -u "$script_dir/export_step_timeseries.py" \
    "$run_dir" \
    "$timeseries_csv" || true
  cp "$run_dir/___RESULT.txt" "$export_dir/" 2>/dev/null || true
  cp "$run_dir/___WINNER.txt" "$export_dir/" 2>/dev/null || true
  cp "$run_dir/param.json" "$export_dir/" 2>/dev/null || true

  python3 -u "$script_dir/plot_topology.py" \
    --topology "$topolog" \
    --islands "$number_of_islands" \
    --result "$run_dir/___RESULT.txt" \
    --output "$export_dir/topology_with_fitness.png" \
    --metrics-output "$export_dir/topology_metrics.json" || true

  python3 -u "$script_dir/summarize_experiments.py" \
    "$run_dir" \
    --output-prefix "$export_dir/summary" || true

  echo "RUN_DIR: $run_dir"
  echo "EXPORT_DIR: $export_dir"

  if [[ "${CLEANUP_RUN_DIR_AFTER_EXPORT:-0}" == "1" ]]; then
    echo "Removing raw run directory after export: $run_dir"
    rm -rf "$run_dir"
  fi
fi

keep_dashboard_seconds="${KEEP_DASHBOARD_SECONDS:-0}"
if [[ "$keep_dashboard_seconds" -gt 0 ]]; then
  echo "Keeping job alive for dashboard: ${keep_dashboard_seconds}s"
  sleep "$keep_dashboard_seconds"
fi
