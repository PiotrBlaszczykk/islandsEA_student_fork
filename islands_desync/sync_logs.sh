#!/bin/bash
set -euo pipefail

# Usage:
#   ./sync_logs.sh
#   REMOTE=plgblaszczykk@login01.ares.cyfronet.pl REMOTE_REPO='~/inteligencja-obliczeniowa/islandsEA_student_fork' ./sync_logs.sh
#
# The SLURM job writes archives to:
#   <repo_root>/log_archives/*.tar.gz
#
# This script downloads those archives and extracts them into:
#   <repo_root>/islands_desync/logs/

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"

remote="${REMOTE:-plgblaszczykk@login01.ares.cyfronet.pl}"
remote_repo="${REMOTE_REPO:-~/inteligencja-obliczeniowa/islandsEA_student_fork}"

local_archive_dir="$repo_root/log_archives"
local_logs_dir="$repo_root/islands_desync/logs"

mkdir -p "$local_archive_dir"
mkdir -p "$local_logs_dir"

echo "Syncing archives from $remote:$remote_repo/log_archives/"
rsync -avh --partial --info=progress2 \
  "$remote:$remote_repo/log_archives/" \
  "$local_archive_dir/" || {
    echo "Archive sync failed or remote archive directory does not exist yet." >&2
  }

shopt -s nullglob
archives=("$local_archive_dir"/*.tar.gz)

if (( ${#archives[@]} > 0 )); then
  echo "Extracting ${#archives[@]} archive(s) into $repo_root/islands_desync"
  for archive in "${archives[@]}"; do
    echo "Extracting $(basename "$archive")"
    tar -xzf "$archive" -C "$repo_root/islands_desync"
  done
else
  echo "No local archives found to extract."
fi

echo "Syncing direct logs as fallback from $remote:$remote_repo/islands_desync/logs/"
rsync -avh --partial --info=progress2 \
  "$remote:$remote_repo/islands_desync/logs/" \
  "$local_logs_dir/" || {
    echo "Direct logs sync failed or remote logs directory does not exist yet." >&2
  }

echo "Logs available in: $local_logs_dir"
echo "Archives available in: $local_archive_dir"
