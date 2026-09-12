#!/usr/bin/env bash
#SBATCH --job-name=islandsea-benchmark
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=6
#SBATCH --mem-per-cpu=2G
#SBATCH --time=00:15:00
#SBATCH --output=slurm-%j.out

set -euo pipefail
: "${SLURM_JOB_ID:?Submit this script with sbatch from the repository root}"
PROJECT_DIR="${ISLANDS_PROJECT_DIR:-${SLURM_SUBMIT_DIR}}"
VENV_DIR="${ISLANDS_VENV_DIR:-${HOME}/venvs/islands-ray}"
CPUS="${SLURM_CPUS_PER_TASK:?Specify --cpus-per-task}"
export ISLANDS_ALLOCATED_CPUS_PER_NODE="$CPUS"
[[ "$CPUS" -ge 2 ]] || { echo 'Need >=2 CPUs per node (one head CPU is reserved for the driver)' >&2; exit 2; }
[[ -f "$PROJECT_DIR/hpc_benchmarks/run_benchmark.py" ]] || { echo 'Submit from the repository root or set ISLANDS_PROJECT_DIR' >&2; exit 2; }
module load python/3.10.4-gcccore-11.3.0
source "$VENV_DIR/bin/activate"
export PYTHONPATH="$PROJECT_DIR/islands_desync${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 MPLBACKEND=Agg
export RAY_DEDUP_LOGS=0
RAY_TMP_DIR="/tmp/${USER}/islandsea-${SLURM_JOB_ID}"
export RAY_TMPDIR="$RAY_TMP_DIR"
export MPLCONFIGDIR="$RAY_TMP_DIR/matplotlib"
mapfile -t NODES < <(scontrol show hostnames "$SLURM_JOB_NODELIST")
HEAD="${NODES[0]}"
read -ra ADDRESSES <<< "$(srun --nodes=1 --ntasks=1 --cpus-per-task=1 -w "$HEAD" hostname -I)"
HEAD_IP="${ADDRESSES[0]}"
PORT="${ISLANDS_RAY_PORT:-$((20000 + SLURM_JOB_ID % 20000))}"
ADDRESS="${HEAD_IP}:${PORT}"
PIDS=()
cleanup() {
    for pid in "${PIDS[@]}"; do kill "$pid" 2>/dev/null || true; done
    wait || true
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
echo "Starting HEAD at $HEAD ($ADDRESS), job=$SLURM_JOB_ID"
srun --exact --nodes=1 --ntasks=1 --cpus-per-task="$CPUS" -w "$HEAD" \
    bash -c 'mkdir -p "$1"; shift; exec "$@"' _ "$RAY_TMP_DIR" \
    "$VENV_DIR/bin/ray" start --head --node-ip-address="$HEAD_IP" --port="$PORT" \
    --num-cpus="$((CPUS - 1))" --temp-dir="$RAY_TMP_DIR" --include-dashboard=false --block &
PIDS+=("$!")
HEAD_READY=0
for attempt in $(seq 1 30); do
    if srun --overlap --nodes=1 --ntasks=1 --cpus-per-task=1 -w "$HEAD" \
        timeout 5 "$VENV_DIR/bin/ray" status --address "$ADDRESS" >/dev/null 2>&1; then
        HEAD_READY=1
        break
    fi
    kill -0 "${PIDS[0]}" 2>/dev/null || { echo 'Ray head exited during startup' >&2; exit 1; }
    sleep 2
done
[[ "$HEAD_READY" == 1 ]] || { echo 'Ray head did not become ready' >&2; exit 1; }
for node in "${NODES[@]:1}"; do
    srun --exact --nodes=1 --ntasks=1 --cpus-per-task="$CPUS" -w "$node" \
        bash -c 'mkdir -p "$1"; shift; exec "$@"' _ "$RAY_TMP_DIR" \
        "$VENV_DIR/bin/ray" start --address="$ADDRESS" --num-cpus="$CPUS" \
        --temp-dir="$RAY_TMP_DIR" --block &
    PIDS+=("$!")
done
# The Ray processes reserve their node's step; the driver shares the head step
# allocation explicitly, using the CPU excluded from head Ray resources.
srun --overlap --nodes=1 --ntasks=1 --cpus-per-task=1 -w "$HEAD" \
    "$VENV_DIR/bin/python" -u "$PROJECT_DIR/hpc_benchmarks/run_benchmark.py" "$@" --ray-address "$ADDRESS"
