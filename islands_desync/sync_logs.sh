#!/bin/bash
set -euo pipefail

# Usage:
#   ./sync_logs.sh
#   REMOTE=plgblaszczykk@login01.ares.cyfronet.pl ./sync_logs.sh
#
# The SLURM job writes archives to:
#   $SCRATCH/islandsEA/results/legacy_delay_archives/*.tar.gz
#
# This script downloads those archives and extracts them into:
#   <workspace>/artifacts/legacy_delay/

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"

remote="${REMOTE:-plgblaszczykk@login01.ares.cyfronet.pl}"
remote_scratch="$(ssh "$remote" 'printf "%s" "$SCRATCH"')"
[[ "$remote_scratch" == /* ]] || {
  echo "Could not resolve remote SCRATCH on $remote" >&2
  exit 2
}

workspace_root="$(cd "$repo_root/../.." && pwd)"
local_archive_dir="${LOCAL_ARCHIVE_DIR:-$workspace_root/artifacts/legacy_delay/archives}"
local_logs_dir="${LOCAL_RESULTS_DIR:-$workspace_root/artifacts/legacy_delay/runs}"

mkdir -p "$local_archive_dir"
mkdir -p "$local_logs_dir"

echo "Syncing archives from $remote:$remote_scratch/islandsEA/results/legacy_delay_archives/"
rsync -avh --partial --info=progress2 \
  "$remote:$remote_scratch/islandsEA/results/legacy_delay_archives/" \
  "$local_archive_dir/" || {
    echo "Archive sync failed or remote archive directory does not exist yet." >&2
  }

shopt -s nullglob
archives=("$local_archive_dir"/*.tar.gz)

if (( ${#archives[@]} > 0 )); then
  echo "Extracting ${#archives[@]} archive(s) into $local_logs_dir"
  for archive in "${archives[@]}"; do
    echo "Extracting $(basename "$archive")"
    tar -xzf "$archive" -C "$local_logs_dir"
  done
else
  echo "No local archives found to extract."
fi

echo "Syncing direct results as fallback from $remote:$remote_scratch/islandsEA/results/runs/"
rsync -avh --partial --info=progress2 \
  "$remote:$remote_scratch/islandsEA/results/runs/" \
  "$local_logs_dir/" || {
    echo "Direct logs sync failed or remote logs directory does not exist yet." >&2
  }

echo "Logs available in: $local_logs_dir"
echo "Archives available in: $local_archive_dir"
