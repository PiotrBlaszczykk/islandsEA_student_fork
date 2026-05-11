# Continuous Benchmarks Workspace

This directory is a student-owned experiment workspace. It is meant to keep
benchmark orchestration, summaries, and topology plots out of the core
algorithm code.

Research question:

```text
Do island topology and migration strategy affect solution quality,
convergence speed, and stability for different objective functions
and island counts?
```

## Files

- `benchmark_matrix_smoke.csv` - very small HPC smoke matrix.
- `benchmark_matrix_template.csv` - starting point for larger experiment plans.
- `benchmark_matrix_full_continuous.csv` - stable continuous benchmark matrix:
  `3 problems x 3 topologies x 4 migrant strategies x 3 island counts x 3 repeats`.
- `generate_full_matrix.py` - regenerates `benchmark_matrix_full_continuous.csv`.
- `run_one_benchmark_hpc.sh` - SLURM wrapper for one benchmark run.
- `submit_matrix.sh` - submits one SLURM job per matrix row.
- `plot_topology.py` - draws topology graphs, optionally colored by final fitness.
- `summarize_experiments.py` - extracts metrics from `___RESULT.txt`, `param.json`,
  and optional `resultsEveryStepW*.json` files.
- `local_smoke_test.py` - local smoke test using already downloaded report artifacts
  when available, with a synthetic fallback.
- `random_topologies/` - deterministic random-topology experiment track. It
  generates frozen JSON adjacency lists plus a separate random-topology matrix.

## Ares workflow

From the outer `islands_desync/` directory on Ares:

```bash
sbatch students_tests/continous_benchmarks/run_one_benchmark_hpc.sh
```

Or submit a matrix:

```bash
bash students_tests/continous_benchmarks/submit_matrix.sh \
  students_tests/continous_benchmarks/benchmark_matrix_smoke.csv
```

Full continuous matrix:

```bash
bash students_tests/continous_benchmarks/submit_matrix.sh \
  students_tests/continous_benchmarks/benchmark_matrix_full_continuous.csv
```

Random-topology matrix:

```bash
python3 students_tests/continous_benchmarks/random_topologies/generate_random_topologies.py

SUBMIT_SLEEP_SECONDS=2 bash students_tests/continous_benchmarks/submit_matrix.sh \
  students_tests/continous_benchmarks/random_topologies/benchmark_matrix_random_topologies.csv
```

For a different SLURM environment, such as another Cyfronet machine, keep the
same matrix but override account/partition at submit time if needed:

```bash
SBATCH_ACCOUNT=<grant> SBATCH_PARTITION=<partition> SUBMIT_SLEEP_SECONDS=2 \
  bash students_tests/continous_benchmarks/submit_matrix.sh \
  students_tests/continous_benchmarks/random_topologies/benchmark_matrix_random_topologies.csv
```

Submit from the repository root or from the outer `islands_desync/` directory.
The wrapper uses `SLURM_SUBMIT_DIR` to find the outer `islands_desync`
runtime directory before calling:

```bash
python3 -u islands_desync/start.py ...
```

This preserves the current runtime assumption used by
`create_algorithm_hpc.py`.

Each SLURM job derives Ray and dashboard ports from `SLURM_JOB_ID`, so several
matrix jobs can run on the same physical node without fighting over port
`6379` or dashboard port `8265`.

When a matrix includes `nodes`, `ntasks`, and `time_limit` columns,
`submit_matrix.sh` passes those resource requests directly to `sbatch`.
The stable full matrix currently uses:

```text
48 islands  ->  4 nodes,  96 tasks, 01:00:00
96 islands  ->  6 nodes, 144 tasks, 01:30:00
144 islands ->  8 nodes, 192 tasks, 02:00:00
```

The earlier `288`-island variant was intentionally removed from the default
matrix after probe runs showed Ray worker crashes on Ares at that scale. Keep
it as a separate stress experiment, not as part of the main reliable batch.

`submit_matrix.sh` waits 1 second between `sbatch` calls by default. Override
with `SUBMIT_SLEEP_SECONDS=0` or a larger value if needed.

## Useful environment overrides

The wrapper forwards these values to the active Ray/HPC path:

```bash
ISLANDS_PROBLEM=sphere
ISLANDS_NUMBER_OF_VARIABLES=30
ISLANDS_NUMBER_OF_EVALUATIONS=600
ISLANDS_POPULATION_SIZE=16
ISLANDS_OFFSPRING_POPULATION_SIZE=4
NUMBER_OF_ISLANDS=12
TOPOLOGY=ring
MIGRANT_STRATEGY=random
MIGRANT_ACCEPT_STRATEGY=BEZ
NUMBER_OF_MIGRANTS=2
MIGRATION_INTERVAL=20
```

Avoid editing the global algorithm configuration for ordinary benchmark
combinations. Prefer matrix rows and environment overrides so each run remains
reproducible.

## Local smoke test

From the repository root:

```bash
python islands_desync/students_tests/continous_benchmarks/local_smoke_test.py
```

It creates `smoke_outputs/` with:

- `smoke_summary.csv`
- `smoke_summary.json`
- `*_topology.png`
- `*_topology_metrics.json`

This does not run Ray. It only validates the analysis pipeline on existing or
synthetic result artifacts.
