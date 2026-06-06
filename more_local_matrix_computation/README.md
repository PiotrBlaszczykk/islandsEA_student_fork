# More Local Matrix Computation

This directory mirrors `local_matrix_computation`, but targets the new
40-benchmark local suite:

- 30 continuous CEC2014 Part A functions: `c01_elliptic` through
  `c30_composition8`.
- 10 binary discrete functions: `d01_labs_binary` through
  `d10_maxcut_ring`.

The GEATbx functions from `some_more_benchmarks.md` are also registered as
optional continuous problems `g01_sphere` through `g16_six_hump_camel` plus
their Matlab-style aliases such as `objfun1`, `objbran`, and `objsixh`. They
are not part of the 120-run default matrix because the requested 40-benchmark
matrix reserves one quarter of the scheduled problems for discrete benchmarks.

The planned local matrix uses all four migrant-selection strategies from the
older local matrix:

```text
random, best, worst, maxDistance
```

Shape:

```text
40 benchmarks x 3 fixed topologies x 4 strategies x 1 repeat = 480 jobs
```

Fixed parameters:

```text
topologies: ring, torus, complete
islands: 12
migrant_strategies: random, best, worst, maxDistance
accept_strategy: plain
continuous variables: 30
discrete bits: 60
evaluations: 1000
population_size: 16
offspring_population_size: 4
migrants: 2
migration_interval: 20
```

The island count is fixed at `12` because the current torus implementation in
the repository assumes a grid width of 12.

## Generate Configs

From the repository root:

```powershell
python more_local_matrix_computation\generate_more_local_matrix_configs.py
```

This creates:

```text
more_local_matrix_computation\runs\manifest.json
more_local_matrix_computation\runs\benchmark_catalog.json
more_local_matrix_computation\runs\all_jobs.json
more_local_matrix_computation\runs\continous_fixed_toplogies\batch_*.json
more_local_matrix_computation\runs\descrete_fixed_toplogies\batch_*.json
```

There are 120 batch files total. Each batch is one benchmark/topology slice and
contains 4 sequential jobs, one for each migrant strategy.

## Validate Definitions

Run this before long benchmark batches:

```powershell
python more_local_matrix_computation\validate_benchmark_definitions.py
```

It checks the 30/10 split, unique four-character log prefixes, problem
construction, single evaluations, and selected known optimum values.

## Dry Run

Inspect the first generated batch:

```powershell
python more_local_matrix_computation\run_batch.py `
  more_local_matrix_computation\runs\continous_fixed_toplogies\batch_001_c01_elliptic_ring_12.json `
  --dry-run
```

Probe a range without executing Ray jobs:

```powershell
python more_local_matrix_computation\run_batch_range.py continous_fixed_toplogies --range 1-5 --dry-run
```

Dry-run the whole 480-job matrix:

```powershell
python more_local_matrix_computation\run_all.py --dry-run
```

## Run Batches

Run one batch:

```powershell
python more_local_matrix_computation\run_batch.py `
  more_local_matrix_computation\runs\continous_fixed_toplogies\batch_001_c01_elliptic_ring_12.json
```

Run a range:

```powershell
python more_local_matrix_computation\run_batch_range.py continous_fixed_toplogies --range 1-10
```

Resume behavior matches `local_matrix_computation`: if an export already has
`summary.csv`, it is skipped unless `--force` is passed.

Run the full 480-job matrix sequentially:

```powershell
python more_local_matrix_computation\run_all.py
```

That command runs the continuous group first and then the descrete group. It
uses `run_batch.py` internally, so results are exported immediately after each
finished job. This makes it safe to resume after interruption: rerun the same
command and finished jobs with `summary.csv` will be skipped.

Run only the first N batch files from the full matrix:

```powershell
python more_local_matrix_computation\run_all.py --limit-batches 5
```

Run the full matrix with an explicit benchmark-job Python:

```powershell
python more_local_matrix_computation\run_all.py `
  --job-python C:\Users\piotr\AppData\Local\Programs\Python\Python310\python.exe
```

## Aggregate Results

After one or more runs finish:

```powershell
python more_local_matrix_computation\aggregate_results.py
```

The wrapper writes aggregate CSV/JSON files under:

```text
more_local_matrix_computation\analysis
```

Raw logs still go through the core algorithm under:

```text
islands_desync\logs\<date_tag>\<problem_prefix><dimension>\<time_tag> ...
```

Friendly exported artifacts go under:

```text
more_local_matrix_computation\results\<group>\<date_tag>\<time_tag>_<benchmark_name>
```
