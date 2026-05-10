#!/bin/bash
# Submit one SLURM job per CSV row.
# Usage:
#   bash students_tests/continous_benchmarks/submit_matrix.sh path/to/matrix.csv

set -euo pipefail

matrix_file="${1:-benchmark_matrix_smoke.csv}"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
runner="${script_dir}/run_one_benchmark_hpc.sh"

if [[ ! -f "$matrix_file" ]]; then
  if [[ -f "${script_dir}/${matrix_file}" ]]; then
    matrix_file="${script_dir}/${matrix_file}"
  else
    echo "Matrix not found: $matrix_file"
    exit 1
  fi
fi

tail -n +2 "$matrix_file" | while IFS=, read -r benchmark_name problem variables evaluations population offspring islands topology migrant_strategy accept_strategy migrants interval repeat nodes ntasks time_limit; do
  benchmark_name="${benchmark_name//$'\r'/}"
  problem="${problem//$'\r'/}"
  variables="${variables//$'\r'/}"
  evaluations="${evaluations//$'\r'/}"
  population="${population//$'\r'/}"
  offspring="${offspring//$'\r'/}"
  islands="${islands//$'\r'/}"
  topology="${topology//$'\r'/}"
  migrant_strategy="${migrant_strategy//$'\r'/}"
  accept_strategy="${accept_strategy//$'\r'/}"
  migrants="${migrants//$'\r'/}"
  interval="${interval//$'\r'/}"
  repeat="${repeat//$'\r'/}"
  nodes="${nodes//$'\r'/}"
  ntasks="${ntasks//$'\r'/}"
  time_limit="${time_limit//$'\r'/}"

  [[ -z "${benchmark_name// }" ]] && continue
  [[ "${benchmark_name:0:1}" == "#" ]] && continue

  if [[ -z "${nodes:-}" || -z "${ntasks:-}" ]]; then
    if [[ "$islands" -le 48 ]]; then
      nodes="${nodes:-4}"
      ntasks="${ntasks:-96}"
    elif [[ "$islands" -le 144 ]]; then
      nodes="${nodes:-8}"
      ntasks="${ntasks:-192}"
    else
      nodes="${nodes:-16}"
      ntasks="${ntasks:-384}"
    fi
  fi

  if [[ -z "${time_limit:-}" ]]; then
    if [[ "$islands" -le 48 ]]; then
      time_limit="01:00:00"
    elif [[ "$islands" -le 144 ]]; then
      time_limit="02:00:00"
    else
      time_limit="04:00:00"
    fi
  fi

  echo "Submitting: $benchmark_name"
  sbatch --job-name="$benchmark_name" --nodes="$nodes" --ntasks="$ntasks" --time="$time_limit" --export=ALL,\
BENCHMARK_NAME="$benchmark_name",\
ISLANDS_PROBLEM="$problem",\
ISLANDS_NUMBER_OF_VARIABLES="$variables",\
ISLANDS_NUMBER_OF_EVALUATIONS="$evaluations",\
ISLANDS_POPULATION_SIZE="$population",\
ISLANDS_OFFSPRING_POPULATION_SIZE="$offspring",\
NUMBER_OF_ISLANDS="$islands",\
TOPOLOGY="$topology",\
MIGRANT_STRATEGY="$migrant_strategy",\
MIGRANT_ACCEPT_STRATEGY="$accept_strategy",\
NUMBER_OF_MIGRANTS="$migrants",\
MIGRATION_INTERVAL="$interval",\
REPEAT="$repeat" \
    "$runner"
  sleep "${SUBMIT_SLEEP_SECONDS:-1}"
done
