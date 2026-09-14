#!/usr/bin/env bash
# Same pinned one-A100 launcher; full suite, 15 minutes, <=0.25 GPUh.
set -euo pipefail
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
exec bash "$SCRIPT_DIR/submit_readiness.sh" --suite "$@"
