#!/usr/bin/env bash
#SBATCH --job-name=island-pilot-gate
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=16G
#SBATCH --time=00:30:00
#SBATCH --partition=plgrid-testing
#SBATCH --account=plglscclass26-cpu
#SBATCH --output=/tmp/island-pilot-gate-%j.out
#SBATCH --error=/tmp/island-pilot-gate-%j.err

# This job runs afterany so it can record and report an invalid canary. The
# strict verifier inside submit_pilot.sh prevents the full allocation unless
# the canary completed with exit 0 and its complete data contract is valid.
set -euo pipefail
[[ "$#" -eq 1 && "$1" =~ ^[0-9]+$ ]] || { echo "Usage: $0 CANARY_JOB_ID" >&2; exit 2; }
: "${SLURM_JOB_ID:?Submit this gate with pilot_run/launch_pilot.sh}"
: "${PILOT_EXPECTED_COMMIT:?Missing pinned pilot commit}"
: "${ISLANDS_PROJECT_DIR:?Missing absolute repository path}"

CANARY_JOB_ID="$1"
case "$ISLANDS_PROJECT_DIR" in
    /*|[A-Za-z]:/*) ;;
    *) echo "ISLANDS_PROJECT_DIR must be an absolute path: $ISLANDS_PROJECT_DIR" >&2; exit 2 ;;
esac
PROJECT_DIR=$(cd -- "$ISLANDS_PROJECT_DIR" && pwd -P) || {
    echo "Invalid ISLANDS_PROJECT_DIR: $ISLANDS_PROJECT_DIR" >&2
    exit 2
}
[[ -f "$PROJECT_DIR/pilot_run/pilot_spec.json" \
    && -f "$PROJECT_DIR/hpc_benchmarks/ares_storage.sh" ]] || {
    echo "ISLANDS_PROJECT_DIR does not point to an IslandsEA checkout: $PROJECT_DIR" >&2
    exit 2
}
export ISLANDS_PROJECT_DIR="$PROJECT_DIR"
SCRIPT_DIR="$PROJECT_DIR/pilot_run"
VENV_DIR="${ISLANDS_VENV_DIR:-${HOME}/venvs/islands-ray}"
source "$PROJECT_DIR/hpc_benchmarks/ares_storage.sh"
islandsea_configure_storage

module load python/3.10.4-gcccore-11.3.0
source "$VENV_DIR/bin/activate"
cd "$PROJECT_DIR"

ACTUAL_COMMIT=$(git rev-parse HEAD)
[[ "$ACTUAL_COMMIT" == "$PILOT_EXPECTED_COMMIT" ]] || {
    echo "GATE_BLOCKED: checkout changed after submission." >&2
    echo "expected=$PILOT_EXPECTED_COMMIT actual=$ACTUAL_COMMIT" >&2
    exit 2
}
[[ -z "$(git status --porcelain --untracked-files=all)" ]] || {
    echo "GATE_BLOCKED: checkout became dirty after submission." >&2
    git status --short >&2
    exit 2
}

ACCOUNTING_READY=0
for _ in $(seq 1 12); do
    CANARY_STATE=$(sacct -n -X -j "$CANARY_JOB_ID" \
        --format=JobIDRaw,State --parsable2 2>/dev/null \
        | awk -F'|' -v id="$CANARY_JOB_ID" '$1 == id {print $2; exit}')
    if [[ -n "$CANARY_STATE" ]]; then
        ACCOUNTING_READY=1
        break
    fi
    sleep 10
done
[[ "$ACCOUNTING_READY" == 1 ]] || {
    echo "PILOT_GATE_FAILED: canary $CANARY_JOB_ID is still absent from sacct after 120 seconds." >&2
    exit 1
}

echo "Validating canary $CANARY_JOB_ID for pinned commit $PILOT_EXPECTED_COMMIT"
echo "canary_state=$CANARY_STATE"
export PILOT_CANARY_JOB_ID="$CANARY_JOB_ID"
export PILOT_EXPECTED_COMMIT
CANARY_DIR="$ISLANDS_ARTIFACT_ROOT/pilot_canaries/$CANARY_JOB_ID"
FULL_SUBMISSION_LOG="$CANARY_DIR/full_submission.txt"
bash "$SCRIPT_DIR/submit_pilot.sh" | tee "$FULL_SUBMISSION_LOG"
ARRAY_JOB_ID=$(awk -F= '/^PILOT_ARRAY_JOB_ID=/{print $2}' "$FULL_SUBMISSION_LOG")
FINALIZER_JOB_ID=$(awk -F= '/^PILOT_FINALIZER_JOB_ID=/{print $2}' "$FULL_SUBMISSION_LOG")
[[ "$ARRAY_JOB_ID" =~ ^[0-9]+$ && "$FINALIZER_JOB_ID" =~ ^[0-9]+$ ]] || {
    echo "PILOT_GATE_FAILED: full submission returned invalid job identifiers." >&2
    exit 1
}
"$VENV_DIR/bin/python" -c '
import json, pathlib, sys
from datetime import datetime, timezone
path = pathlib.Path(sys.argv[1])
payload = json.loads(path.read_text(encoding="utf-8"))
payload.update({
    "status": "full_pilot_submitted",
    "gate_completed_utc": datetime.now(timezone.utc).isoformat(),
    "array_job_id": sys.argv[2],
    "finalizer_job_id": sys.argv[3],
})
path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
' "$CANARY_DIR/pipeline_submission.json" "$ARRAY_JOB_ID" "$FINALIZER_JOB_ID"
echo "PILOT_GATE_OK"
