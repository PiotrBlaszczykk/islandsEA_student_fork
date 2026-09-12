#!/usr/bin/env bash
set -uo pipefail

DIAG_USER="${USER:?USER is not set}"
DIAG_PROJECT_DIR="/net/people/plgrid/plgblaszczykk/islandsEA_student_fork"
DIAG_VENV_DIR="/net/people/plgrid/plgblaszczykk/venvs/islands-ray"
DIAG_ARTIFACT_DIR="/net/people/plgrid/plgblaszczykk/artifacts/diagnostics"
DIAG_TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
DIAG_REPORT="${DIAG_ARTIFACT_DIR}/ares_diagnostics_${DIAG_TIMESTAMP}.txt"
DIAG_RECENT_START="$(date -d '7 days ago' +%F)"

mkdir -p "${DIAG_ARTIFACT_DIR}"

section() {
    printf '\n===== %s =====\n' "$1"
}

run_command() {
    local title="$1"
    shift
    section "${title}"
    printf 'COMMAND:'
    printf ' %q' "$@"
    printf '\n'
    "$@" 2>&1
    local status=$?
    if [[ ${status} -ne 0 ]]; then
        printf 'COMMAND_FAILED exit=%s\n' "${status}"
    fi
    return 0
}

{
    section "REPORT"
    echo "generated_at=$(date --iso-8601=seconds)"
    echo "report=${DIAG_REPORT}"
    echo "requested_job_ids=${*:-none}"

    run_command "IDENTITY" id
    run_command "HOSTNAME" hostname -f
    run_command "KERNEL" uname -a
    run_command "CURRENT DIRECTORY" pwd
    run_command "RESOURCE LIMITS" bash -c 'ulimit -a'
    run_command "CPU DESCRIPTION" lscpu

    section "ENVIRONMENT VARIABLES"
    env | grep -E '^(SLURM|PLG|MODULE|LMOD|PATH|LD_LIBRARY_PATH|VIRTUAL_ENV)=' | sort || true

    section "MODULES"
    module list 2>&1 || true
    module -t avail python/3.10.4-gcccore-11.3.0 2>&1 || true

    run_command "SLURM VERSION" srun --version
    run_command "PARTITION SUMMARY" sinfo -o '%P|availability=%a|limit=%l|nodes=%D|cpus/node=%c|memory/node_MB=%m|gres=%G'
    run_command "PARTITION DETAILS" scontrol show partition
    run_command "CURRENT QUEUE" squeue -u "${DIAG_USER}" -o '%.18i %.12P %.28j %.10T %.12M %.6D %R'
    run_command "PRIORITY" sprio -u "${DIAG_USER}" -l

    section "SLURM ACCOUNT ASSOCIATIONS"
    sacctmgr -nP show user "${DIAG_USER}" withassoc \
        format=User,DefaultAccount,Account,Partition,QOS 2>&1 || true

    section "SLURM ACCOUNT LIMITS"
    sacctmgr -nP show assoc where user="${DIAG_USER}" \
        format=Cluster,Account,Partition,QOS,DefaultQOS,GrpTRES,GrpTRESMins,MaxTRES,MaxTRESMins,MaxJobs,MaxSubmitJobs 2>&1 || true

    run_command "FAIRSHARE" sshare -l -u "${DIAG_USER}"

    section "SELECTED SLURM CONFIG"
    scontrol show config 2>&1 | grep -E \
        '^(AccountingStorageTRES|DefMemPerCPU|MaxArraySize|MaxJobCount|MaxMemPerCPU|SelectType|SelectTypeParameters|SlurmctldVersion)' || true

    section "RECENT JOBS SINCE ${DIAG_RECENT_START}"
    sacct -S "${DIAG_RECENT_START}" -u "${DIAG_USER}" -X -P \
        --format=JobIDRaw,JobName,Partition,Account,State,ExitCode,ElapsedRaw,AllocCPUS,CPUTimeRAW,NodeList 2>&1 || true

    section "FILESYSTEMS"
    df -h \
        "/net/people/plgrid/plgblaszczykk" \
        "${DIAG_PROJECT_DIR}" \
        "${DIAG_ARTIFACT_DIR}" \
        /tmp 2>&1 || true

    run_command "QUOTA" quota -s

    section "DIRECTORY SIZES"
    du -sh \
        "${DIAG_PROJECT_DIR}" \
        "/net/people/plgrid/plgblaszczykk/artifacts" \
        "${DIAG_VENV_DIR}" 2>&1 || true

    section "GIT"
    git -C "${DIAG_PROJECT_DIR}" status --short --branch 2>&1 || true
    git -C "${DIAG_PROJECT_DIR}" log -5 --date=iso-strict \
        --pretty=format:'%H|%ad|%s' 2>&1 || true
    printf '\n'

    section "PYTHON MODULE LOAD"
    module load python/3.10.4-gcccore-11.3.0 2>&1 || true

    section "PROJECT VENV"
    if [[ -x "${DIAG_VENV_DIR}/bin/python" ]]; then
        "${DIAG_VENV_DIR}/bin/python" - <<'PY'
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
    "ray",
    "jmetalpy",
    "numpy",
    "scipy",
    "scikit-learn",
    "pandas",
    "matplotlib",
    "setuptools",
    "wheel",
    "packaging",
):
    try:
        version = importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        version = "NOT_INSTALLED"
    print(f"{package}: {version}")
PY
        run_command "PIP CHECK" "${DIAG_VENV_DIR}/bin/python" -m pip check
    else
        echo "MISSING_VENV_PYTHON=${DIAG_VENV_DIR}/bin/python"
    fi

    for diag_job_id in "$@"; do
        section "JOB ${diag_job_id}: SACCT"
        sacct -j "${diag_job_id}" -P \
            --format=JobIDRaw,JobName,Partition,Account,State,ExitCode,ElapsedRaw,AllocCPUS,CPUTimeRAW,TotalCPU,MaxRSS,ReqMem,NodeList 2>&1 || true

        if command -v seff >/dev/null 2>&1; then
            run_command "JOB ${diag_job_id}: SEFF" seff "${diag_job_id}"
        fi

        diag_nodes="$(sacct -j "${diag_job_id}" -nX -P --format=NodeList 2>/dev/null | head -n 1 | cut -d'|' -f1)"
        if [[ -n "${diag_nodes}" && "${diag_nodes}" != "None assigned" ]]; then
            section "JOB ${diag_job_id}: NODE DESCRIPTION"
            scontrol show node "${diag_nodes}" 2>&1 || true
        fi
    done
} | tee "${DIAG_REPORT}"

echo
echo "DIAGNOSTICS_READY=${DIAG_REPORT}"

