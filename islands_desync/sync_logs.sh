#!/bin/bash
set -euo pipefail

# Usage:
#   ./sync_logs.sh
#   REMOTE=plglkwinta@athena.cyfronet.pl REMOTE_REPO='~/islandsEA_student_fork' ./sync_logs.sh
#
# This script syncs raw experiment logs from:
#   <remote_repo>/islands_desync/logs/
# into:
#   <repo_root>/islands_desync/logs/

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"

remote="${REMOTE:-plglkwinta@athena.cyfronet.pl}"
remote_repo="${REMOTE_REPO:-~/islandsEA_student_fork}"

local_logs_dir="$repo_root/islands_desync/logs"

mkdir -p "$local_logs_dir"

echo "Syncing raw logs from $remote:$remote_repo/islands_desync/logs/"
rsync -avh --partial --info=progress2 \
  "$remote:$remote_repo/islands_desync/logs/" \
  "$local_logs_dir/" || {
    echo "Raw logs sync failed or remote logs directory does not exist yet." >&2
    exit 2
  }

echo "Logs available in: $local_logs_dir"
