#!/bin/bash
# Parametric SLURM script for delay experiments across topologies.
#
#SBATCH --job-name=islands-delay
#SBATCH --nodes=10
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=40
#SBATCH --time=00:30:00
#SBATCH --mem-per-cpu=500M
#SBATCH -p plgrid
#SBATCH -A plglscclass26-cpu
#SBATCH --output=slurm-%j.out

set -euo pipefail
set -x

if [[ ! -f "islands_desync/start.py" ]]; then
    echo "ERROR: Run this script from the outer islands_desync/ directory." >&2
    exit 1
fi

repo_root="$(cd .. && pwd)"
venv_path="${VENV_PATH:-$repo_root/.venv}"

module load Python/3.10.4

if [[ ! -x "$venv_path/bin/python" ]]; then
    echo "Creating virtualenv at $venv_path ..."
    python -m venv "$venv_path"
    source "$venv_path/bin/activate"
    python -m pip install -r "$repo_root/islands_desync/islands_desync/geneticAlgorithm/algorithm/requirements.txt" \
        ray==2.9.3 scikit-learn==1.1.3 'setuptools<81' 'click<8.2'
fi

source "$venv_path/bin/activate"
python -m pip install --quiet 'click<8.2'

tmpdir="/tmp/$USER/$SLURM_JOB_ID"
mkdir -p "$tmpdir"

export TMPDIR="$tmpdir"
export RAY_TMPDIR="$tmpdir"
export ISLANDS_MPLCONFIGDIR_BASE="${ISLANDS_MPLCONFIGDIR_BASE:-$tmpdir/matplotlib}"
export ISLANDS_SHARED_MPLCONFIGDIR="${ISLANDS_SHARED_MPLCONFIGDIR:-0}"
export MPLCONFIGDIR="$ISLANDS_MPLCONFIGDIR_BASE"

cleanup() {
    echo "Cleaning up Ray and temporary directory"
    ray stop --force || true
    rm -rf "$tmpdir" || true
}

trap cleanup EXIT

export MPLBACKEND=Agg
export PYTHONPATH="$PWD:${PYTHONPATH:-}"

mkdir -p "$ISLANDS_MPLCONFIGDIR_BASE"
mkdir -p logs

python --version
python -c "import ray; print('ray', ray.__version__)"

nodes=$(scontrol show hostnames "$SLURM_JOB_NODELIST")
nodes_array=($nodes)

srun --nodes="$SLURM_JOB_NUM_NODES" --ntasks="$SLURM_JOB_NUM_NODES" \
    mkdir -p "$tmpdir" "$ISLANDS_MPLCONFIGDIR_BASE"

raw_cpus_per_node="${RAY_CPUS_PER_NODE:-${SLURM_CPUS_PER_TASK:-${SLURM_CPUS_ON_NODE:-48}}}"
ray_cpus_per_node="${raw_cpus_per_node%%(*}"
ray_cpus_per_node="${ray_cpus_per_node%%,*}"

if [[ ! "$ray_cpus_per_node" =~ ^[0-9]+$ ]]; then
    echo "WARNING: Could not infer CPUs per node from '$raw_cpus_per_node', falling back to 1." >&2
    ray_cpus_per_node=1
fi

head_node=${nodes_array[0]}
head_node_ip=$(srun --nodes=1 --ntasks=1 -w "$head_node" hostname --ip-address | awk '{print $1}')

port=6379
ip_head="$head_node_ip:$port"
export ip_head

echo "IP Head: $ip_head"
echo "Ray CPUs per node: $ray_cpus_per_node"
echo "Starting Ray HEAD at $head_node"

srun --nodes=1 --ntasks=1 --cpus-per-task="$ray_cpus_per_node" -w "$head_node" \
    ray start --head --node-ip-address="$head_node_ip" --port="$port" \
    --num-cpus="$ray_cpus_per_node" --temp-dir="$tmpdir" --block &

sleep 10

worker_num=$((SLURM_JOB_NUM_NODES - 1))
for ((i = 1; i <= worker_num; i++)); do
    node_i=${nodes_array[$i]}
    echo "Starting Ray WORKER $i at $node_i"
    srun --nodes=1 --ntasks=1 --cpus-per-task="$ray_cpus_per_node" -w "$node_i" \
        --export=ALL,RAY_TMPDIR="$tmpdir" \
        ray start --address "$ip_head" --num-cpus="$ray_cpus_per_node" --block &
    sleep 5
done

echo "Waiting for Ray workers to connect"
sleep 20

number_of_islands="${NUMBER_OF_ISLANDS:-150}"
number_of_migrants="${NUMBER_OF_MIGRANTS:-5}"
migration_interval="${MIGRATION_INTERVAL:-5}"
topology="${TOPOLOGY:-ring}"
selection_strategy="${SELECTION_STRATEGY:-random}"
acceptance_strategy="${ACCEPTANCE_STRATEGY:-plain}"

dda=$(date +%y%m%d)

rep="${REPETITION:-1}"
topology_safe="${topology//:/-}"
strategy_safe="${acceptance_strategy//:/-}"
tta="$(date +%H%M%S)_${topology_safe}_${strategy_safe}_r${rep}_j${SLURM_JOB_ID}"

echo "=== EXPERIMENT: topology=$topology strategy=$acceptance_strategy islands=$number_of_islands ==="

python -u islands_desync/start.py \
    "$number_of_islands" \
    "$tmpdir" \
    "$number_of_migrants" \
    "$migration_interval" \
    "$dda" \
    "$tta" \
    "$topology" \
    "$selection_strategy" \
    "$acceptance_strategy"

problem_dir="logs/$dda/Sphe200"
migrant_code="${selection_strategy:0:1}"
topology_code="${topology:0:1}"
run_dir="$problem_dir/$tta ${number_of_islands}${migrant_code}${topology_code}-co${migration_interval}ilu${number_of_migrants}"

echo "Run directory: $run_dir"

archive_dir="$repo_root/log_archives"
mkdir -p "$archive_dir"

strat_safe="${acceptance_strategy//:/-}"
archive_name="${dda}_${tta}_${number_of_islands}${migrant_code}${topology_code}-co${migration_interval}ilu${number_of_migrants}_${selection_strategy}_${strat_safe}_job${SLURM_JOB_ID}.tar.gz"
archive_path="$archive_dir/$archive_name"

if [[ -d "$run_dir" ]]; then
    python analyze_migration_delays.py "$run_dir" || true
else
    echo "ERROR: run_dir does not exist: $run_dir" >&2
    exit 2
fi

tar -czf "$archive_path" "$run_dir"

ray stop --force || true

echo "Done. Archive: $archive_path"
exit 0
