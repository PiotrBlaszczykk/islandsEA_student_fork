#!/usr/bin/env bash

# Collect the scheduler/login-node view first, then (by default) submit one
# short A100 allocation whose output is appended to the same report.
set -uo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PROJECT_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)
DIAG_USER="${USER:-$(id -un)}"
DIAG_VENV_DIR="${ISLANDS_VENV_DIR:-${HOME}/venvs/islands-ray}"
DIAG_REPORT="${ATHENA_DIAGNOSTICS_REPORT:-${HOME}/artifacts/athena_duagnostics.txt}"
DIAG_RECENT_START="$(date -d '7 days ago' +%F)"
DIAG_LOG_ROOT="${ATHENA_DIAGNOSTICS_LOG_ROOT:-${SCRATCH:-${HOME}/artifacts}/islandsEA/logs/slurm}"
ATHENA_ACCOUNT="${ATHENA_ACCOUNT:-plglscclass26-gpu-a100}"
ATHENA_PARTITION="${ATHENA_PARTITION:-plgrid-gpu-a100}"
ATHENA_GRES="${ATHENA_GRES:-gpu:1}"
ATHENA_CPUS_PER_TASK="${ATHENA_CPUS_PER_TASK:-16}"
ATHENA_MEMORY="${ATHENA_MEMORY:-128000M}"
ATHENA_PROBE_TIME="${ATHENA_PROBE_TIME:-00:10:00}"
SUBMIT_GPU_PROBE=1
JOB_IDS=()

usage() {
    cat <<'EOF'
Usage: bash athena_diagnostics/collect_athena_info.sh [--login-only] [JOB_ID ...]

Default: collect login-node diagnostics and submit a minimal one-A100 probe.
Use --login-only to collect only read-only login/scheduler information.

Optional environment overrides:
  ATHENA_ACCOUNT, ATHENA_PARTITION, ATHENA_GRES,
  ATHENA_CPUS_PER_TASK, ATHENA_MEMORY, ATHENA_PROBE_TIME,
  ATHENA_DIAGNOSTICS_REPORT, ATHENA_DIAGNOSTICS_LOG_ROOT,
  ISLANDS_VENV_DIR.
EOF
}

for argument in "$@"; do
    case "$argument" in
        --login-only) SUBMIT_GPU_PROBE=0 ;;
        -h|--help) usage; exit 0 ;;
        *[!0-9]*|'') echo "Invalid argument: $argument" >&2; usage >&2; exit 2 ;;
        *) JOB_IDS+=("$argument") ;;
    esac
done

mkdir -p "$(dirname -- "$DIAG_REPORT")" "$DIAG_LOG_ROOT"

section() {
    printf '\n===== %s =====\n' "$1"
}

run_command() {
    local title="$1"
    shift
    section "$title"
    printf 'COMMAND:'
    printf ' %q' "$@"
    printf '\n'
    "$@" 2>&1
    local status=$?
    if [[ "$status" -ne 0 ]]; then
        printf 'COMMAND_FAILED exit=%s\n' "$status"
    fi
    return 0
}

filesystem_report() {
    local label="$1"
    local path="$2"
    [[ -n "$path" ]] || return 0
    section "FILESYSTEM: $label"
    echo "path=$path"
    if [[ -e "$path" ]]; then
        df -h "$path" 2>&1 || true
        df -i "$path" 2>&1 || true
    else
        echo "PATH_NOT_FOUND"
    fi
}

{
    section "ATHENA DIAGNOSTICS REPORT"
    echo "schema_version=1"
    echo "generated_at=$(date --iso-8601=seconds)"
    echo "report=$DIAG_REPORT"
    echo "project_dir=$PROJECT_DIR"
    echo "venv_dir=$DIAG_VENV_DIR"
    echo "submit_gpu_probe=$SUBMIT_GPU_PROBE"
    echo "requested_job_ids=${JOB_IDS[*]:-none}"

    run_command "IDENTITY" id
    run_command "HOSTNAME" hostname -f
    run_command "KERNEL" uname -a
    run_command "OS RELEASE" bash -c 'cat /etc/os-release'
    run_command "GLIBC" bash -c 'ldd --version | head -n 2'
    run_command "CURRENT DIRECTORY" pwd
    run_command "RESOURCE LIMITS" bash -c 'ulimit -a'
    run_command "LOGIN CPU DESCRIPTION" lscpu
    run_command "LOGIN MEMORY" free -h

    section "RELEVANT ENVIRONMENT VARIABLES"
    env | grep -E '^(SLURM|PLG|SCRATCH|HOME|MODULE|LMOD|PATH|LD_LIBRARY_PATH|VIRTUAL_ENV|CUDA|NVIDIA|RAY|UCX|NCCL)=' \
        | sort || true

    section "COMMAND AVAILABILITY"
    for command_name in \
        sbatch srun salloc squeue sinfo scontrol sacct sacctmgr sshare sprio seff \
        hpc-grants hpc-fs module python python3 nvidia-smi nvcc \
        ibstat ibv_devinfo ucx_info numactl lspci; do
        if command -v "$command_name" >/dev/null 2>&1; then
            printf '%s=%s\n' "$command_name" "$(command -v "$command_name")"
        else
            printf '%s=NOT_FOUND\n' "$command_name"
        fi
    done

    section "LOADED MODULES"
    module list 2>&1 || true

    section "RELEVANT AVAILABLE MODULES"
    module -t avail 2>&1 \
        | grep -Ei '(^|/)(python|cuda|cudnn|nccl|gcc|nvhpc|openmpi|ucx|ray|pytorch|tensorflow|cupy)' \
        | head -n 500 || true

    run_command "SLURM VERSION" srun --version
    run_command "HPC GRANTS" hpc-grants
    run_command "HPC FILESYSTEMS" hpc-fs
    run_command "PARTITION SUMMARY" sinfo -o '%P|availability=%a|limit=%l|nodes=%D|cpus/node=%c|memory/node_MB=%m|gres=%G|features=%f'
    run_command "GPU NODE SUMMARY" bash -c \
        "sinfo -N -h -o '%N|%P|state=%t|cpus=%c|memory_MB=%m|gres=%G|features=%f' | grep -i gpu || true"
    run_command "A100 PARTITION DETAILS" scontrol show partition "$ATHENA_PARTITION"
    run_command "CURRENT QUEUE" squeue -u "$DIAG_USER" -o '%.18i %.20P %.28j %.10T %.12M %.6D %.8C %b %R'
    run_command "PRIORITY" sprio -u "$DIAG_USER" -l

    section "SLURM ACCOUNT ASSOCIATIONS"
    sacctmgr -nP show user "$DIAG_USER" withassoc \
        format=User,DefaultAccount,Account,Partition,QOS 2>&1 || true

    section "SLURM ACCOUNT LIMITS"
    sacctmgr -nP show assoc where user="$DIAG_USER" \
        format=Cluster,Account,Partition,QOS,DefaultQOS,GrpTRES,GrpTRESMins,MaxTRES,MaxTRESMins,MaxJobs,MaxSubmitJobs 2>&1 || true

    run_command "FAIRSHARE" sshare -l -u "$DIAG_USER"

    section "SELECTED SLURM CONFIG"
    scontrol show config 2>&1 | grep -E \
        '^(AccountingStorageTRES|GresTypes|MaxArraySize|MaxJobCount|SelectType|SelectTypeParameters|SlurmctldVersion|TaskPlugin)' || true

    section "RECENT JOBS SINCE $DIAG_RECENT_START"
    sacct -S "$DIAG_RECENT_START" -u "$DIAG_USER" -X -P \
        --format=JobIDRaw,JobName,Partition,Account,State,ExitCode,ElapsedRaw,AllocCPUS,AllocTRES,ReqTRES,CPUTimeRAW,NodeList 2>&1 || true

    filesystem_report "HOME" "${HOME:-}"
    filesystem_report "SCRATCH" "${SCRATCH:-}"
    filesystem_report "PLG_GROUPS_STORAGE" "${PLG_GROUPS_STORAGE:-}"
    filesystem_report "PLG_GROUPS_SCRATCH" "${PLG_GROUPS_SCRATCH:-}"
    filesystem_report "PROJECT" "$PROJECT_DIR"
    filesystem_report "TMP" /tmp
    run_command "QUOTA" quota -s

    section "DIRECTORY SIZES"
    du -sh "$PROJECT_DIR" "${HOME}/artifacts" "${HOME}/venvs" 2>&1 || true
    if [[ -n "${SCRATCH:-}" && -e "${SCRATCH}/islandsEA" ]]; then
        du -sh "${SCRATCH}/islandsEA" 2>&1 || true
    fi

    section "GIT"
    git -C "$PROJECT_DIR" status --short --branch 2>&1 || true
    git -C "$PROJECT_DIR" remote -v 2>&1 || true
    git -C "$PROJECT_DIR" log -5 --date=iso-strict \
        --pretty=format:'%H|%ad|%s' 2>&1 || true
    printf '\n'

    section "DISCOVERED VIRTUAL ENVIRONMENTS"
    find "${HOME}/venvs" -maxdepth 3 -type f -path '*/bin/python' -print 2>&1 || true

    section "PROJECT VENV"
    if [[ -x "$DIAG_VENV_DIR/bin/python" ]]; then
        "$DIAG_VENV_DIR/bin/python" - <<'PY'
import importlib.metadata
import os
import platform
import socket
import sys

print("host:", socket.gethostname())
print("python:", sys.version.replace("\n", " "))
print("executable:", sys.executable)
print("prefix:", sys.prefix)
print("platform:", platform.platform())
print("cpu_count:", os.cpu_count())
for package in (
    "ray", "jmetalpy", "numpy", "scipy", "scikit-learn", "pandas",
    "matplotlib", "setuptools", "wheel", "packaging", "torch", "cupy",
    "tensorflow", "jax", "jaxlib", "numba",
):
    try:
        version = importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        version = "NOT_INSTALLED"
    print(f"{package}: {version}")
PY
        run_command "PIP CHECK" "$DIAG_VENV_DIR/bin/python" -m pip check
    else
        echo "MISSING_VENV_PYTHON=$DIAG_VENV_DIR/bin/python"
    fi

    section "LOGIN-NODE NVIDIA VISIBILITY (NONE IS EXPECTED)"
    nvidia-smi -L 2>&1 || echo "NO_LOGIN_GPU"

    for diag_job_id in "${JOB_IDS[@]}"; do
        section "JOB ${diag_job_id}: SACCT"
        sacct -j "$diag_job_id" -P \
            --format=JobIDRaw,JobName,Partition,Account,State,ExitCode,ElapsedRaw,AllocCPUS,AllocTRES,ReqTRES,CPUTimeRAW,TotalCPU,MaxRSS,ReqMem,NodeList 2>&1 || true
        if command -v seff >/dev/null 2>&1; then
            run_command "JOB ${diag_job_id}: SEFF" seff "$diag_job_id"
        fi
        diag_nodes=$(sacct -j "$diag_job_id" -nX -P --format=NodeList 2>/dev/null | head -n 1 | cut -d'|' -f1)
        if [[ -n "$diag_nodes" && "$diag_nodes" != "None assigned" ]]; then
            section "JOB ${diag_job_id}: NODE DESCRIPTION"
            scontrol show node "$diag_nodes" 2>&1 || true
        fi
    done

    section "PLANNED GPU PROBE"
    echo "account=$ATHENA_ACCOUNT"
    echo "partition=$ATHENA_PARTITION"
    echo "gres=$ATHENA_GRES"
    echo "cpus_per_task=$ATHENA_CPUS_PER_TASK"
    echo "memory=$ATHENA_MEMORY"
    echo "time_limit=$ATHENA_PROBE_TIME"
    echo "ATHENA_LOGIN_DIAGNOSTICS_COMPLETE=1"
} | tee "$DIAG_REPORT"

if [[ "$SUBMIT_GPU_PROBE" == 0 ]]; then
    echo "ATHENA_DIAGNOSTICS_READY=$DIAG_REPORT"
    echo "GPU probe was not submitted (--login-only)."
    exit 0
fi

SBATCH_OUTPUT=$(sbatch --parsable --hold \
    --job-name=islandsea-athena-diagnostics \
    --nodes=1 \
    --ntasks=1 \
    --cpus-per-task="$ATHENA_CPUS_PER_TASK" \
    --mem="$ATHENA_MEMORY" \
    --time="$ATHENA_PROBE_TIME" \
    --partition="$ATHENA_PARTITION" \
    --account="$ATHENA_ACCOUNT" \
    --gres="$ATHENA_GRES" \
    --output="$DIAG_LOG_ROOT/athena-diagnostics-%j.out" \
    --error="$DIAG_LOG_ROOT/athena-diagnostics-%j.err" \
    --export="ALL,ATHENA_DIAGNOSTICS_REPORT=${DIAG_REPORT},ATHENA_PROJECT_DIR=${PROJECT_DIR},ISLANDS_VENV_DIR=${DIAG_VENV_DIR}" \
    "$SCRIPT_DIR/run_gpu_probe.sh" 2>&1)
SBATCH_STATUS=$?

if [[ "$SBATCH_STATUS" -ne 0 ]]; then
    {
        section "GPU PROBE SUBMISSION FAILED"
        echo "$SBATCH_OUTPUT"
        echo "ATHENA_GPU_PROBE_SUBMITTED=0"
    } | tee -a "$DIAG_REPORT"
    echo "ATHENA_DIAGNOSTICS_READY=$DIAG_REPORT"
    exit "$SBATCH_STATUS"
fi

PROBE_JOB_ID="${SBATCH_OUTPUT%%;*}"
if [[ ! "$PROBE_JOB_ID" =~ ^[0-9]+$ ]]; then
    {
        section "GPU PROBE SUBMISSION FAILED"
        echo "Could not parse job id from: $SBATCH_OUTPUT"
        echo "ATHENA_GPU_PROBE_SUBMITTED=0"
    } | tee -a "$DIAG_REPORT"
    exit 1
fi

{
    section "GPU PROBE SUBMISSION"
    echo "ATHENA_GPU_PROBE_JOB_ID=$PROBE_JOB_ID"
    echo "ATHENA_GPU_PROBE_SUBMITTED=1"
    echo "probe_log=$DIAG_LOG_ROOT/athena-diagnostics-$PROBE_JOB_ID.out"
    echo "probe_error=$DIAG_LOG_ROOT/athena-diagnostics-$PROBE_JOB_ID.err"
    echo "The report is complete only after ATHENA_GPU_PROBE_COMPLETE=1 appears."
} | tee -a "$DIAG_REPORT"

if ! scontrol release "$PROBE_JOB_ID"; then
    {
        section "GPU PROBE RELEASE FAILED"
        echo "The held job must be released or cancelled manually: $PROBE_JOB_ID"
    } | tee -a "$DIAG_REPORT"
    exit 1
fi

echo "ATHENA_DIAGNOSTICS_READY=$DIAG_REPORT"
echo "ATHENA_GPU_PROBE_JOB_ID=$PROBE_JOB_ID"
echo "Monitor: squeue -j $PROBE_JOB_ID"
echo "After completion: sacct -j $PROBE_JOB_ID --format=JobID,State,ExitCode,Elapsed,AllocCPUS,AllocTRES,ReqTRES,NodeList"
echo "Completion marker: grep ATHENA_GPU_PROBE_COMPLETE '$DIAG_REPORT'"
