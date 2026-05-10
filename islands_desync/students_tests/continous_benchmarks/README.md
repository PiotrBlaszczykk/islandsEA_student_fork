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
- `run_one_benchmark_hpc.sh` - SLURM wrapper for one benchmark run.
- `submit_matrix.sh` - submits one SLURM job per matrix row.
- `plot_topology.py` - draws topology graphs, optionally colored by final fitness.
- `summarize_experiments.py` - extracts metrics from `___RESULT.txt`, `param.json`,
  and optional `resultsEveryStepW*.json` files.
- `local_smoke_test.py` - local smoke test using already downloaded report artifacts
  when available, with a synthetic fallback.

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
