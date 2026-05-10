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

tail -n +2 "$matrix_file" | while IFS=, read -r benchmark_name problem variables evaluations population offspring islands topology migrant_strategy accept_strategy migrants interval repeat; do
  [[ -z "${benchmark_name// }" ]] && continue
  [[ "${benchmark_name:0:1}" == "#" ]] && continue

  echo "Submitting: $benchmark_name"
  sbatch --export=ALL,\
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
done

