#!/usr/bin/env bash

# Shared Ares storage contract. Source this file before submitting a job and
# again inside the allocation. Every path can be overridden independently.
islandsea_configure_storage() {
    local storage_base
    if [[ -n "${SCRATCH:-}" ]]; then
        storage_base="$SCRATCH"
        export ISLANDS_STORAGE_FALLBACK=0
    else
        : "${HOME:?HOME is required when SCRATCH is not defined}"
        storage_base="$HOME"
        export ISLANDS_STORAGE_FALLBACK=1
        echo "WARNING: SCRATCH is not defined; generated data will use $HOME/islandsEA" >&2
    fi

    export ISLANDS_STORAGE_ROOT="${ISLANDS_STORAGE_ROOT:-$storage_base/islandsEA}"
    export ISLANDS_RESULTS_ROOT="${ISLANDS_RESULTS_ROOT:-$ISLANDS_STORAGE_ROOT/results}"
    export ISLANDS_LOG_ROOT="${ISLANDS_LOG_ROOT:-$ISLANDS_STORAGE_ROOT/logs}"
    export ISLANDS_CHECKPOINT_ROOT="${ISLANDS_CHECKPOINT_ROOT:-$ISLANDS_STORAGE_ROOT/checkpoints}"
    export ISLANDS_TMP_ROOT="${ISLANDS_TMP_ROOT:-$ISLANDS_STORAGE_ROOT/tmp}"

    export ISLANDS_RUN_OUTPUT_ROOT="${ISLANDS_RUN_OUTPUT_ROOT:-$ISLANDS_RESULTS_ROOT/runs}"
    export ISLANDS_AUDIT_ROOT="${ISLANDS_AUDIT_ROOT:-$ISLANDS_RESULTS_ROOT/audit}"
    export ISLANDS_ARTIFACT_ROOT="${ISLANDS_ARTIFACT_ROOT:-$ISLANDS_RESULTS_ROOT/pilot_runs}"
    export ISLANDS_SLURM_LOG_DIR="${ISLANDS_SLURM_LOG_DIR:-$ISLANDS_LOG_ROOT/slurm}"
    export ISLANDS_RAY_FAILURE_ROOT="${ISLANDS_RAY_FAILURE_ROOT:-$ISLANDS_LOG_ROOT/ray_failures}"

    mkdir -p \
        "$ISLANDS_RUN_OUTPUT_ROOT" \
        "$ISLANDS_AUDIT_ROOT" \
        "$ISLANDS_ARTIFACT_ROOT" \
        "$ISLANDS_SLURM_LOG_DIR" \
        "$ISLANDS_RAY_FAILURE_ROOT" \
        "$ISLANDS_CHECKPOINT_ROOT" \
        "$ISLANDS_TMP_ROOT"
}

islandsea_print_storage() {
    printf '%s\n' \
        "ISLANDS_STORAGE_ROOT=$ISLANDS_STORAGE_ROOT" \
        "ISLANDS_RESULTS_ROOT=$ISLANDS_RESULTS_ROOT" \
        "ISLANDS_LOG_ROOT=$ISLANDS_LOG_ROOT" \
        "ISLANDS_CHECKPOINT_ROOT=$ISLANDS_CHECKPOINT_ROOT" \
        "ISLANDS_TMP_ROOT=$ISLANDS_TMP_ROOT" \
        "ISLANDS_RUN_OUTPUT_ROOT=$ISLANDS_RUN_OUTPUT_ROOT" \
        "ISLANDS_AUDIT_ROOT=$ISLANDS_AUDIT_ROOT" \
        "ISLANDS_ARTIFACT_ROOT=$ISLANDS_ARTIFACT_ROOT" \
        "ISLANDS_SLURM_LOG_DIR=$ISLANDS_SLURM_LOG_DIR"
}
