#!/usr/bin/env bash

# One-command Ares launcher. It performs a local preflight, submits the canary
# and schedules a lightweight validation gate. The gate submits the expensive
# three-repeat pilot only after the canary is complete and fully valid.
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PROJECT_DIR=$(cd -- "$SCRIPT_DIR/.." && pwd)
VENV_DIR="${ISLANDS_VENV_DIR:-${HOME}/venvs/islands-ray}"
CONFIRMATION="${1:-}"
MAX_PARALLEL="${PILOT_MAX_PARALLEL:-3}"

[[ "$#" -eq 1 && "$CONFIRMATION" == "--confirm-144-and-562-cpuh" ]] || {
    cat >&2 <<'EOF'
Usage: bash pilot_run/launch_pilot.sh --confirm-144-and-562-cpuh

This authorizes the approved 144-island / 12x12 torus pilot allocation:
  * canary: 7 x 48 CPUs, 10 min walltime (maximum 56 CPUh),
  * full pilot after a valid canary: 3 x 7 x 48 CPUs, 30 min walltime
    (maximum 504 CPUh),
  * finalizer: maximum 1 CPUh.
The combined safety ceiling is 561.5 CPUh (rounded up to 562); no automatic retry.
EOF
    exit 2
}

[[ -z "${SLURM_JOB_ID:-}" ]] || {
    echo "Run this launcher on an Ares login node, not inside an allocation." >&2
    exit 2
}
command -v sbatch >/dev/null || { echo "sbatch is unavailable; run this on Ares." >&2; exit 2; }
command -v module >/dev/null || { echo "Environment Modules are unavailable; run this on Ares." >&2; exit 2; }
[[ "$MAX_PARALLEL" =~ ^[1-3]$ ]] || {
    echo "PILOT_MAX_PARALLEL must be 1, 2 or 3." >&2
    exit 2
}

source "$PROJECT_DIR/hpc_benchmarks/ares_storage.sh"
islandsea_configure_storage
[[ "${ISLANDS_STORAGE_FALLBACK:-1}" == "0" && -n "${SCRATCH:-}" ]] || {
    echo "Submission blocked: SCRATCH must be defined; HOME fallback is not allowed for the pilot." >&2
    exit 2
}
case "$ISLANDS_STORAGE_ROOT/" in
    "$SCRATCH"/*) ;;
    *)
        echo "Submission blocked: ISLANDS_STORAGE_ROOT must be below SCRATCH." >&2
        echo "SCRATCH=$SCRATCH" >&2
        echo "ISLANDS_STORAGE_ROOT=$ISLANDS_STORAGE_ROOT" >&2
        exit 2
        ;;
esac

module load python/3.10.4-gcccore-11.3.0
[[ -x "$VENV_DIR/bin/python" ]] || { echo "Missing project venv: $VENV_DIR" >&2; exit 2; }
source "$VENV_DIR/bin/activate"

cd "$PROJECT_DIR"
[[ -z "$(git status --porcelain --untracked-files=all)" ]] || {
    echo "Submission blocked: the Git working tree is not clean." >&2
    git status --short >&2
    exit 2
}
BRANCH=$(git branch --show-current)
[[ "$BRANCH" == "summer_benchmarks_ares" ]] || {
    echo "Submission blocked: expected branch summer_benchmarks_ares, found ${BRANCH:-detached HEAD}." >&2
    exit 2
}
COMMIT=$(git rev-parse HEAD)
UPSTREAM=$(git rev-parse '@{upstream}' 2>/dev/null) || {
    echo "Submission blocked: branch $BRANCH has no upstream." >&2
    exit 2
}
[[ "$COMMIT" == "$UPSTREAM" ]] || {
    echo "Submission blocked: HEAD differs from the locally known upstream." >&2
    echo "Run: git pull --ff-only origin summer_benchmarks_ares" >&2
    exit 2
}

echo "=== PILOT PREFLIGHT ==="
echo "branch=$BRANCH"
echo "commit=$COMMIT"
echo "venv=$VENV_DIR"
islandsea_print_storage
df -h "$SCRATCH"
df -i "$SCRATCH"

"$VENV_DIR/bin/python" -m unittest pilot_run.test_pilot_tools
mapfile -t BENCHMARK_ARGS < <(
    "$VENV_DIR/bin/python" "$SCRIPT_DIR/pilot_tools.py" benchmark-args --repeat 1
)
[[ "${#BENCHMARK_ARGS[@]}" -gt 0 ]] || {
    echo "Pilot configuration produced no benchmark arguments." >&2
    exit 2
}
PLAN_JSON=$("$VENV_DIR/bin/python" "$PROJECT_DIR/hpc_benchmarks/run_benchmark.py" \
    "${BENCHMARK_ARGS[@]}" --dry-run)
printf '%s\n' "$PLAN_JSON"
"$VENV_DIR/bin/python" -c '
import json, sys
p = json.loads(sys.argv[1])
expected = {"islands": 144, "dimension": 200, "required_ray_cpus": 289, "required_slurm_cpus": 290}
bad = {key: (p.get(key), value) for key, value in expected.items() if p.get(key) != value}
if bad:
    raise SystemExit(f"Invalid dry-run resource plan: {bad}")
print("PILOT_DRY_RUN_OK")
' "$PLAN_JSON"

export ISLANDS_PROJECT_DIR="$PROJECT_DIR"
export PILOT_EXPECTED_COMMIT="$COMMIT"
CANARY_OUTPUT=$(bash "$SCRIPT_DIR/submit_canary.sh")
printf '%s\n' "$CANARY_OUTPUT"
CANARY_JOB_ID=$(awk -F= '/^PILOT_CANARY_JOB_ID=/{print $2}' <<<"$CANARY_OUTPUT")
[[ "$CANARY_JOB_ID" =~ ^[0-9]+$ ]] || {
    echo "Could not extract the canary job id; refusing to schedule the continuation." >&2
    exit 1
}

GATE_SUBMISSION=$(sbatch --parsable \
    --dependency="afterany:${CANARY_JOB_ID}" \
    --output="$ISLANDS_SLURM_LOG_DIR/pilot-gate-%j.out" \
    --error="$ISLANDS_SLURM_LOG_DIR/pilot-gate-%j.err" \
    --export="ALL,ISLANDS_PROJECT_DIR=${PROJECT_DIR},ISLANDS_ARTIFACT_ROOT=${ISLANDS_ARTIFACT_ROOT},ISLANDS_VENV_DIR=${VENV_DIR},PILOT_EXPECTED_COMMIT=${COMMIT},PILOT_MAX_PARALLEL=${MAX_PARALLEL}" \
    "$SCRIPT_DIR/continue_after_canary.sh" "$CANARY_JOB_ID")
GATE_JOB_ID="${GATE_SUBMISSION%%;*}"
[[ "$GATE_JOB_ID" =~ ^[0-9]+$ ]] || {
    echo "Could not extract the validation-gate job id." >&2
    exit 1
}

CANARY_DIR="$ISLANDS_ARTIFACT_ROOT/pilot_canaries/$CANARY_JOB_ID"
mkdir -p "$CANARY_DIR"
"$VENV_DIR/bin/python" -c '
import json, pathlib, sys
from datetime import datetime, timezone
path = pathlib.Path(sys.argv[1])
payload = {
    "schema_version": 1,
    "created_utc": datetime.now(timezone.utc).isoformat(),
    "status": "canary_and_gate_submitted",
    "branch": sys.argv[2],
    "git_commit": sys.argv[3],
    "canary_job_id": sys.argv[4],
    "gate_job_id": sys.argv[5],
    "max_parallel_repeats": int(sys.argv[6]),
    "artifact_root": sys.argv[7],
    "slurm_log_dir": sys.argv[8],
    "automatic_full_submit": True,
    "automatic_retry": False,
}
path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
' "$CANARY_DIR/pipeline_submission.json" "$BRANCH" "$COMMIT" \
  "$CANARY_JOB_ID" "$GATE_JOB_ID" "$MAX_PARALLEL" \
  "$ISLANDS_ARTIFACT_ROOT" "$ISLANDS_SLURM_LOG_DIR"

echo "=== PILOT PIPELINE SUBMITTED ==="
echo "PILOT_CANARY_JOB_ID=$CANARY_JOB_ID"
echo "PILOT_GATE_JOB_ID=$GATE_JOB_ID"
echo "PIPELINE_METADATA=$CANARY_DIR/pipeline_submission.json"
echo "GATE_LOG=$ISLANDS_SLURM_LOG_DIR/pilot-gate-$GATE_JOB_ID.out"
echo "The gate will submit the full 3-repeat pilot only after strict canary validation."
echo "Monitor: squeue -j $CANARY_JOB_ID,$GATE_JOB_ID"
echo "Accounting: sacct -j $CANARY_JOB_ID,$GATE_JOB_ID --format=JobID,JobName,State,ExitCode,Elapsed,AllocCPUS,CPUTimeRAW,MaxRSS"
