#!/usr/bin/env bash
#SBATCH --job-name=torus-best-finalize
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=16G
#SBATCH --time=04:00:00
#SBATCH --partition=plgrid
#SBATCH --account=plglscclass26-cpu
#SBATCH --output=/tmp/torus-best-finalize-%j.out
#SBATCH --error=/tmp/torus-best-finalize-%j.err

set -euo pipefail
STRATEGY="${ISLANDS_CAMPAIGN_STRATEGY:-best}"
[[ "$STRATEGY" == best || "$STRATEGY" == random ]] || {
    echo "Unsupported campaign strategy: $STRATEGY" >&2
    exit 2
}
export ISLANDS_CAMPAIGN_STRATEGY="$STRATEGY"
[[ "$#" -ge 1 && "$#" -le 2 ]] || {
    echo "Usage: $0 CAMPAIGN_ARRAY_JOB_ID [RETRY_ARRAY_JOB_ID]" >&2
    exit 2
}
: "${ISLANDS_PROJECT_DIR:?Missing absolute repository path}"
: "${ISLANDS_CAMPAIGN_DIR:?Missing absolute campaign path}"
case "$ISLANDS_PROJECT_DIR:$ISLANDS_CAMPAIGN_DIR" in
    /*:/*) ;;
    *) echo "Project and campaign paths must be absolute" >&2; exit 2 ;;
esac

ARRAY_JOB_ID="$1"
ACCOUNTING_JOB_IDS="$ARRAY_JOB_ID"
[[ "$#" -eq 1 ]] || ACCOUNTING_JOB_IDS="$ARRAY_JOB_ID,$2"
PROJECT_DIR=$(cd -- "$ISLANDS_PROJECT_DIR" && pwd -P)
CAMPAIGN_DIR=$(cd -- "$ISLANDS_CAMPAIGN_DIR" && pwd -P)
VENV_DIR="${ISLANDS_VENV_DIR:-${HOME}/venvs/islands-ray}"
TOOLS="$PROJECT_DIR/main_runs/campaign_tools.py"
[[ -f "$TOOLS" && -x "$VENV_DIR/bin/python" ]] || {
    echo "Missing campaign tools or Ares venv" >&2
    exit 2
}
cd "$PROJECT_DIR"
[[ -z "$(git status --porcelain --untracked-files=all)" ]] || {
    echo "Campaign finalizer blocked: checkout is dirty" >&2
    git status --short >&2
    exit 2
}

module load python/3.10.4-gcccore-11.3.0
source "$VENV_DIR/bin/activate"
sacct -n -P -j "$ACCOUNTING_JOB_IDS" \
    --format=JobIDRaw,JobName,Partition,State,ExitCode,ElapsedRaw,AllocCPUS,CPUTimeRAW,TotalCPU,MaxRSS,MaxVMSize,AveRSS,ReqMem,NodeList \
    > "$CAMPAIGN_DIR/sacct.txt" || true

"$VENV_DIR/bin/python" "$TOOLS" finalize \
    --campaign-dir "$CAMPAIGN_DIR" \
    --array-job-id "$ARRAY_JOB_ID"
echo "TORUS_${STRATEGY^^}_FINALIZATION_OK"
