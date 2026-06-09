#!/bin/bash
#SBATCH --job-name=islands-delay
#SBATCH --nodes=4
#SBATCH --ntasks=400
#SBATCH --ntasks-per-node=100
#SBATCH --time=0:50:00
#SBATCH --mem-per-cpu=250M
#SBATCH -p plgrid-gpu-a100
#SBATCH -A plgintobl-gpu-a100
#SBATCH --output=slurm-%j.out

set -euo pipefail
set -x

# Submit from the outer islands_desync/ directory:
#   cd /path/to/islandsEA_student_fork/islands_desync
#   sbatch run_local_venv_plgrid_now.sh

if [[ ! -f "islands_desync/start.py" ]]; then
    echo "Run this script from the outer islands_desync/ directory." >&2
    exit 1
fi

repo_root="$(cd .. && pwd)"
venv_path="${VENV_PATH:-$repo_root/.venv}"

module load Python/3.10.4

if [[ ! -x "$venv_path/bin/python" ]]; then
    echo "Missing Python executable at $venv_path/bin/python" >&2
    
    python -m venv "$venv_path"
    source "$venv_path/bin/activate"

    python -m pip install -r "$repo_root/islands_desync/islands_desync/geneticAlgorithm/algorithm/requirements.txt" ray==2.9.3 scikit-learn==1.1.3 'setuptools<81' 'click<8.2'
fi

source "$venv_path/bin/activate"

# Ray 2.9.x CLI breaks with newer Click releases on this cluster stack.
python -m pip install --quiet 'click<8.2'

tmpdir="/tmp/$USER/$SLURM_JOB_ID"
mkdir -p "$tmpdir"

export TMPDIR="$tmpdir"
export RAY_TMPDIR="$tmpdir"
export ISLANDS_MPLCONFIGDIR_BASE="${ISLANDS_MPLCONFIGDIR_BASE:-$tmpdir/matplotlib}"
export ISLANDS_SHARED_MPLCONFIGDIR="${ISLANDS_SHARED_MPLCONFIGDIR:-0}"
export MPLCONFIGDIR="$ISLANDS_MPLCONFIGDIR_BASE"
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

raw_cpus_per_node="${RAY_CPUS_PER_NODE:-${SLURM_JOB_CPUS_PER_NODE:-${SLURM_CPUS_ON_NODE:-${SLURM_NTASKS_PER_NODE:-1}}}}"
ray_cpus_per_node="${raw_cpus_per_node%%(*}"
ray_cpus_per_node="${ray_cpus_per_node%%,*}"

if [[ ! "$ray_cpus_per_node" =~ ^[0-9]+$ ]]; then
    echo "Could not infer CPUs per node from '$raw_cpus_per_node', falling back to 1." >&2
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
    ray start --head --node-ip-address="$head_node_ip" --port="$port" --num-cpus="$ray_cpus_per_node" --temp-dir="$tmpdir" --block &

sleep 10

worker_num=$((SLURM_JOB_NUM_NODES - 1))

for ((i = 1; i <= worker_num; i++)); do
    node_i=${nodes_array[$i]}
    echo "Starting Ray WORKER $i at $node_i"
    srun --nodes=1 --ntasks=1 --cpus-per-task="$ray_cpus_per_node" -w "$node_i" --export=ALL,RAY_TMPDIR="$tmpdir" \
        ray start --address "$ip_head" --num-cpus="$ray_cpus_per_node" --block &
    sleep 5
done

number_of_islands="${NUMBER_OF_ISLANDS:-150}"
number_of_migrants="${NUMBER_OF_MIGRANTS:-5}"
migration_interval="${MIGRATION_INTERVAL:-5}"
topology="${TOPOLOGY:-ring}"
selection_strategy="${SELECTION_STRATEGY:-random}"
acceptance_strategy="${ACCEPTANCE_STRATEGY:-plain}"
dda=$(date +%y%m%d)
tta=$(date +%H%M%S)

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

ray stop --force || true

echo "Done. Raw logs are in: logs/$dda"

exit 0
