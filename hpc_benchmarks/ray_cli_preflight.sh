#!/usr/bin/env bash

# Source this file and call islandsea_validate_ray_cli before reserving nodes.
# Ray 2.9.3 imports its complete Click command tree even for `ray --version`,
# so this catches CLI dependency drift without starting Ray or using SLURM.
islandsea_validate_ray_cli() {
    local venv_dir="${1:?Pass the project venv directory}"
    local versions ray_output

    [[ -x "$venv_dir/bin/python" && -x "$venv_dir/bin/ray" ]] || {
        echo "Ray CLI preflight failed: missing $venv_dir/bin/python or $venv_dir/bin/ray" >&2
        return 2
    }

    versions=$("$venv_dir/bin/python" -c '
import importlib.metadata
print(
    "ray=" + importlib.metadata.version("ray"),
    "click=" + importlib.metadata.version("click"),
)
') || {
        echo "Ray CLI preflight failed while reading package versions from $venv_dir" >&2
        return 2
    }
    echo "RAY_RUNTIME_VERSIONS $versions"

    if ! ray_output=$("$venv_dir/bin/ray" --version 2>&1); then
        printf '%s\n' "$ray_output" >&2
        echo "Ray CLI preflight failed before submission." >&2
        echo "The validated Ares environment requires ray==2.9.3 with click==8.2.1." >&2
        echo "Repair the existing venv with:" >&2
        printf '  %q -m pip install %q\n' "$venv_dir/bin/python" 'click==8.2.1' >&2
        return 2
    fi
    echo "RAY_CLI_PREFLIGHT_OK $ray_output"
}
