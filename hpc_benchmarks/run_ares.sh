#!/usr/bin/env bash
#SBATCH --job-name=islandsea-benchmark
#SBATCH --nodes=7
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=48
#SBATCH --mem-per-cpu=2G
#SBATCH --time=00:15:00
#SBATCH --output=/tmp/islandsea-benchmark-%j.out
#SBATCH --error=/tmp/islandsea-benchmark-%j.err

set -euo pipefail
: "${SLURM_JOB_ID:?Submit this script with sbatch from the repository root}"
BENCHMARK_ARGS=("$@")
PROJECT_DIR="${ISLANDS_PROJECT_DIR:-${SLURM_SUBMIT_DIR}}"
RUNTIME_DIR="$PROJECT_DIR/islands_desync"
VENV_DIR="${ISLANDS_VENV_DIR:-${HOME}/venvs/islands-ray}"
source "$PROJECT_DIR/hpc_benchmarks/ares_storage.sh"
islandsea_configure_storage
CPUS="${SLURM_CPUS_PER_TASK:?Specify --cpus-per-task}"
export ISLANDS_ALLOCATED_CPUS_PER_NODE="$CPUS"
[[ "$CPUS" -ge 2 ]] || { echo 'Need >=2 CPUs per node (one head CPU is reserved for the driver)' >&2; exit 2; }
[[ -f "$PROJECT_DIR/hpc_benchmarks/run_benchmark.py" ]] || { echo 'Submit from the repository root or set ISLANDS_PROJECT_DIR' >&2; exit 2; }
[[ -f "$RUNTIME_DIR/islands_desync/geneticAlgorithm/run_algorithm.py" ]] || { echo "Invalid runtime directory: $RUNTIME_DIR" >&2; exit 2; }
module load python/3.10.4-gcccore-11.3.0
source "$VENV_DIR/bin/activate"
export PYTHONPATH="$PROJECT_DIR/islands_desync${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 MPLBACKEND=Agg
export RAY_DEDUP_LOGS=0
RAY_TMP_DIR="/tmp/${USER}/islandsea-${SLURM_JOB_ID}"
export RAY_TMPDIR="$RAY_TMP_DIR"
export TMPDIR="$RAY_TMP_DIR/tmp"
export XDG_CACHE_HOME="$RAY_TMP_DIR/xdg-cache"
export MPLCONFIGDIR="$RAY_TMP_DIR/matplotlib"
islandsea_print_storage
mapfile -t NODES < <(scontrol show hostnames "$SLURM_JOB_NODELIST")
NODE_COUNT="${#NODES[@]}"
[[ "$NODE_COUNT" -eq "${SLURM_JOB_NUM_NODES:?Missing SLURM_JOB_NUM_NODES}" ]] || {
    echo "SLURM node list has $NODE_COUNT nodes, expected $SLURM_JOB_NUM_NODES" >&2
    exit 2
}

# Validate the complete benchmark configuration and its actor resource demand
# before starting any persistent Ray process. The JSON is also useful evidence
# in the SLURM log when a launch is rejected.
PLAN_JSON=$("$VENV_DIR/bin/python" -u "$PROJECT_DIR/hpc_benchmarks/run_benchmark.py" \
    "${BENCHMARK_ARGS[@]}" --dry-run)
printf '%s\n' "$PLAN_JSON"
read -r ISLAND_COUNT REQUIRED_RAY_CPUS REQUIRED_SLURM_CPUS < <(
    "$VENV_DIR/bin/python" -c \
        'import json, sys; p=json.loads(sys.argv[1]); print(p["islands"], p["required_ray_cpus"], p["required_slurm_cpus"])' \
        "$PLAN_JSON"
)
ALLOCATED_CPUS=$((NODE_COUNT * CPUS))
AVAILABLE_RAY_CPUS=$((ALLOCATED_CPUS - 1))
echo "RESOURCE_PLAN islands=$ISLAND_COUNT nodes=$NODE_COUNT cpus_per_node=$CPUS allocated_cpus=$ALLOCATED_CPUS available_ray_cpus=$AVAILABLE_RAY_CPUS required_ray_cpus=$REQUIRED_RAY_CPUS required_slurm_cpus=$REQUIRED_SLURM_CPUS"
if (( AVAILABLE_RAY_CPUS < REQUIRED_RAY_CPUS )); then
    echo "Insufficient allocation: $ISLAND_COUNT islands need at least $REQUIRED_SLURM_CPUS SLURM CPUs ($REQUIRED_RAY_CPUS for Ray plus one driver CPU); allocated $ALLOCATED_CPUS" >&2
    exit 2
fi

HEAD="${NODES[0]}"
read -ra ADDRESSES <<< "$(srun --nodes=1 --ntasks=1 --cpus-per-task=1 -w "$HEAD" hostname -I)"
HEAD_IP="${ADDRESSES[0]}"
PORT="${ISLANDS_RAY_PORT:-$((20000 + SLURM_JOB_ID % 20000))}"
ADDRESS="${HEAD_IP}:${PORT}"
PIDS=()
cleanup() {
    local status=$?
    local remove_tmp=1
    trap - EXIT INT TERM
    set +e
    for pid in "${PIDS[@]}"; do kill "$pid" 2>/dev/null || true; done
    wait || true
    if (( status != 0 )); then
        local failure_dir="${ISLANDS_RAY_FAILURE_DIR:-$ISLANDS_RAY_FAILURE_ROOT/$SLURM_JOB_ID}"
        mkdir -p "$failure_dir"
        echo "Job failed; collecting per-node Ray logs in $failure_dir" >&2
        timeout 60 srun --overlap --exact --nodes="$NODE_COUNT" --ntasks="$NODE_COUNT" \
            --ntasks-per-node=1 --cpus-per-task=1 \
            bash -c 'tmp="$1"; out="$2"; host=$(hostname -s); if [[ -d "$tmp/session_latest/logs" ]]; then tar -chzf "$out/ray-${host}.tar.gz" -C "$tmp/session_latest" logs; fi' \
            _ "$RAY_TMP_DIR" "$failure_dir" >/dev/null 2>&1 || {
                echo "Warning: Ray failure-log collection failed; preserving $RAY_TMP_DIR on compute nodes" >&2
                remove_tmp=0
            }
    fi
    if (( remove_tmp == 1 )) && [[ "$RAY_TMP_DIR" == "/tmp/${USER}/islandsea-${SLURM_JOB_ID}" ]]; then
        timeout 30 srun --overlap --exact --nodes="$NODE_COUNT" --ntasks="$NODE_COUNT" \
            --ntasks-per-node=1 --cpus-per-task=1 \
            bash -c 'expected="/tmp/${USER}/islandsea-${SLURM_JOB_ID}"; [[ "$1" == "$expected" ]] || exit 2; rm -rf -- "$1"' \
            _ "$RAY_TMP_DIR" >/dev/null 2>&1 || echo "Warning: could not remove $RAY_TMP_DIR from every node" >&2
    fi
    exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# Matplotlib is imported by every Computation worker through the historical GA
# module graph. Build its font/config cache once on each node so hundreds of
# workers only read a completed node-local cache instead of racing to create it.
echo "Prewarming Matplotlib cache on $NODE_COUNT nodes at $MPLCONFIGDIR"
srun --exact --nodes="$NODE_COUNT" --ntasks="$NODE_COUNT" --ntasks-per-node=1 --cpus-per-task=1 \
    bash -c 'mkdir -p "$1/tmp" "$1/xdg-cache"; cd "$2"; shift 2; exec "$@"' _ "$RAY_TMP_DIR" "$RUNTIME_DIR" "$VENV_DIR/bin/python" -c \
    'import socket; from islands_desync.geneticAlgorithm.utils.matplotlib_setup import configure_headless_matplotlib; p=configure_headless_matplotlib(); import matplotlib.pyplot as plt; f=plt.figure(); plt.close(f); print(f"MPL_CACHE_READY host={socket.gethostname()} path={p}")'

echo "Starting HEAD at $HEAD ($ADDRESS), job=$SLURM_JOB_ID"
srun --exact --nodes=1 --ntasks=1 --cpus-per-task="$CPUS" -w "$HEAD" \
    bash -c 'mkdir -p "$1/tmp" "$1/xdg-cache"; cd "$2"; shift 2; exec "$@"' _ "$RAY_TMP_DIR" "$RUNTIME_DIR" \
    "$VENV_DIR/bin/ray" start --head --node-ip-address="$HEAD_IP" --port="$PORT" \
    --num-cpus="$((CPUS - 1))" --temp-dir="$RAY_TMP_DIR" --include-dashboard=false --block &
PIDS+=("$!")
HEAD_READY=0
HEAD_STATUS_LOG="$RAY_TMP_DIR/ray-status.log"
for attempt in $(seq 1 30); do
    # The batch shell already runs on SLURM's first node, which is the Ray
    # head. Starting another srun step here can be rejected or delayed while
    # the blocking head step owns that node, even when Ray itself is healthy.
    if timeout 5 "$VENV_DIR/bin/ray" status --address="$ADDRESS" \
        >"$HEAD_STATUS_LOG" 2>&1; then
        HEAD_READY=1
        echo "RAY_HEAD_READY address=$ADDRESS attempt=$attempt"
        break
    fi
    kill -0 "${PIDS[0]}" 2>/dev/null || { echo 'Ray head exited during startup' >&2; exit 1; }
    sleep 2
done
if [[ "$HEAD_READY" != 1 ]]; then
    echo "Ray head did not become ready; last status output:" >&2
    cat "$HEAD_STATUS_LOG" >&2 || true
    exit 1
fi
for node in "${NODES[@]:1}"; do
    srun --exact --nodes=1 --ntasks=1 --cpus-per-task="$CPUS" -w "$node" \
        bash -c 'mkdir -p "$1/tmp" "$1/xdg-cache"; cd "$2"; shift 2; exec "$@"' _ "$RAY_TMP_DIR" "$RUNTIME_DIR" \
        "$VENV_DIR/bin/ray" start --address="$ADDRESS" --num-cpus="$CPUS" \
        --temp-dir="$RAY_TMP_DIR" --block &
    PIDS+=("$!")
done
# The Ray processes reserve their node's step; the driver shares the head step
# allocation explicitly, using the CPU excluded from head Ray resources.
srun --overlap --exact --nodes=1 --ntasks=1 --cpus-per-task=1 -w "$HEAD" \
    bash -c 'cd "$1"; shift; exec "$@"' _ "$RUNTIME_DIR" \
    "$VENV_DIR/bin/python" -u "$PROJECT_DIR/hpc_benchmarks/run_benchmark.py" \
    "${BENCHMARK_ARGS[@]}" --ray-address "$ADDRESS"
