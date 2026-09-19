#!/usr/bin/env bash
# Shared CPU/GPU post-run packaging. Source after PROJECT_DIR/VENV_DIR setup.
islandsea_bundle_prepare() {
    ISLANDS_BUNDLE_PLATFORM="$1"
    shift
    ISLANDS_BUNDLE_POINTER="${ISLANDS_RESULTS_ROOT}/job_evidence/${SLURM_JOB_ID}/result_pointer.json"
    while (( $# )); do
        case "$1" in
            --result-pointer)
                [[ $# -ge 2 ]] || { echo 'Missing --result-pointer value' >&2; return 2; }
                ISLANDS_BUNDLE_POINTER="$2"; shift 2 ;;
            --result-pointer=*) ISLANDS_BUNDLE_POINTER="${1#*=}"; shift ;;
            *) shift ;;
        esac
    done
    ISLANDS_BUNDLE_JOB_DIR=$(dirname -- "$ISLANDS_BUNDLE_POINTER")
    export ISLANDS_EXPORT_ROOT="${ISLANDS_EXPORT_ROOT:-$ISLANDS_STORAGE_ROOT/exports}"
    mkdir -p "$ISLANDS_BUNDLE_JOB_DIR" "$ISLANDS_EXPORT_ROOT"
}

islandsea_bundle_finish() {
    local status="$1"
    local -a options=(
        export --platform "$ISLANDS_BUNDLE_PLATFORM" --job-id "$SLURM_JOB_ID"
        --pointer "$ISLANDS_BUNDLE_POINTER" --job-dir "$ISLANDS_BUNDLE_JOB_DIR"
        --log-dir "$ISLANDS_SLURM_LOG_DIR" --output-root "$ISLANDS_EXPORT_ROOT"
        --exit-code "$status" --replace
    )
    (( status == 0 )) || options+=(--allow-incomplete)
    if [[ -d "${ISLANDS_RAY_FAILURE_DIR:-}" ]]; then
        options+=(--ray-logs "$ISLANDS_RAY_FAILURE_DIR")
    fi
    if ! "$VENV_DIR/bin/python" "$PROJECT_DIR/hpc_benchmarks/run_bundle.py" "${options[@]}"; then
        echo "RUN_BUNDLE_FAILED=$SLURM_JOB_ID; original scientific outputs retained" >&2
        return 74
    fi
    echo "RUN_BUNDLE_ARCHIVE=$ISLANDS_EXPORT_ROOT/run_${SLURM_JOB_ID}.tar.gz"
}

islandsea_bundle_early_exit() {
    local status=$?
    trap - EXIT
    set +e
    if [[ "${ISLANDS_BUNDLE_DEFER:-0}" != 1 ]]; then
        islandsea_bundle_finish "$status"
        local bundle_status=$?
        if (( status == 0 && bundle_status != 0 )); then status=$bundle_status; fi
    fi
    exit "$status"
}
