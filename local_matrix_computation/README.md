# Local Matrix Computation

This directory contains the local replacement for the Ares/SLURM benchmark
matrix. It runs the same style of island-model experiments, but scaled down so
they can finish on a desktop/laptop without burning HPC allocation.

The directory names intentionally keep the historical typos used elsewhere in
the project:

```text
continous_fixed_toplogies
continous_random_topologies
descrete_fixed_toplogies
descrete_random_topologies
```

Do not rename those folders casually; configs and result paths depend on them.

## Mental Model

One **job** is one benchmark run:

```text
problem + topology + island_count + migrant_strategy + repeat
```

One **batch** is 12 jobs:

```text
one problem + one topology + one island_count
x 4 migrant strategies
x 3 repeats
= 12 jobs
```

One **group** is 324 jobs:

```text
3 problems x 3 topologies x 3 island counts x 4 strategies x 3 repeats
= 324 jobs
```

There are four groups, so the whole local experiment is 1296 jobs. Do not run
the whole thing blindly.

## Local Parameters

Continuous groups:

```text
problems: sphere, rastrigin, ackley
topologies: ring, torus, complete
random topologies: rt_er_d4_s1, rt_er_d8_s1, rt_ws_k4_p010_s1
islands: 12, 24, 36
variables: 30
evaluations: 1000
population_size: 16
offspring_population_size: 4
migrants: 2
migration_interval: 20
accept_strategy: BEZ
```

Discrete groups:

```text
problems: labs_binary, trap5, nk_k4
topologies: ring, torus, complete
random topologies: rt_er_d4_s1, rt_er_d8_s1, rt_ws_k4_p010_s1
islands: 12, 24, 36
bits: 60
evaluations: 1000
population_size: 16
offspring_population_size: 4
migrants: 2
migration_interval: 20
accept_strategy: BEZ
```

Random topology JSON files are deterministic and live in:

```text
local_matrix_computation/runs/random_topologies/graphs
```

## Environment

Use the local venv from the repository root:

```powershell
.\.venv\Scripts\Activate.ps1
```

If Ray was interrupted or the terminal looks weird after `Ctrl+C`, clean it up:

```powershell
.\.venv\Scripts\ray.exe stop --force
```

The local runner also tries to stop Ray before and after each job, but the
manual command above is useful after a hard interrupt.

## Regenerate Configs

From the repository root:

```powershell
python local_matrix_computation\generate_local_matrix_configs.py
```

This creates:

```text
local_matrix_computation\runs\manifest.json
local_matrix_computation\runs\all_jobs.json
local_matrix_computation\runs\<group>\manifest.json
local_matrix_computation\runs\<group>\all_jobs.json
local_matrix_computation\runs\<group>\batch_*.json
local_matrix_computation\runs\random_topologies\graphs\*.json
```

Smoke configs are separate:

```powershell
python local_matrix_computation\smoke_run\generate_smoke_configs.py
```

Smoke documentation lives in:

```text
local_matrix_computation/smoke_run/README.md
```

## Recommended First Run

Before running production batches, verify one tiny smoke job:

```powershell
Measure-Command { python local_matrix_computation\run_batch.py local_matrix_computation\smoke_run\runs\continous_fixed_toplogies\smoke_batch.json --force --limit 1 }
```

Observed local reference from 2026-05-13:

```text
1 continuous fixed smoke job: about 40 seconds
```

That smoke job is much smaller than a production job.

## Recommended First Production Batch

The safest production batch is:

```text
local_matrix_computation\runs\continous_fixed_toplogies\batch_001_sphere_ring_12.json
```

It runs:

```text
sphere + ring + 12 islands
x random, best, worst, maxDistance
x 3 repeats
= 12 jobs
```

Run it with a timestamped log:

```powershell
$batch = "local_matrix_computation\runs\continous_fixed_toplogies\batch_001_sphere_ring_12.json"
$log = "local_matrix_computation\runs\continous_fixed_toplogies\batch_001_sphere_ring_12_$(Get-Date -Format yyyyMMdd_HHmmss).log"

Measure-Command {
  python local_matrix_computation\run_batch.py $batch 2>&1 | Tee-Object -FilePath $log
}
```

Use this when going away from the terminal. Make sure the machine is plugged in
and Windows sleep is disabled.

## Dry Run

Always inspect an unfamiliar batch first:

```powershell
python local_matrix_computation\run_batch.py local_matrix_computation\runs\continous_fixed_toplogies\batch_001_sphere_ring_12.json --dry-run
```

Dry-run prints the exact `run_local_benchmark.py` commands without running Ray.

## Running and Resuming

Normal run:

```powershell
python local_matrix_computation\run_batch.py local_matrix_computation\runs\continous_fixed_toplogies\batch_001_sphere_ring_12.json
```

Resume behavior:

- if `summary.csv` already exists, the job is skipped;
- this is useful after an interrupted batch;
- do not add `--force` when you want resume behavior.

Overwrite behavior:

```powershell
python local_matrix_computation\run_batch.py local_matrix_computation\runs\continous_fixed_toplogies\batch_001_sphere_ring_12.json --force
```

`--force` reruns jobs even when `summary.csv` exists. It also tells the inner
runner to remove the expected raw log directory and export directory first.

Run only the first N jobs:

```powershell
python local_matrix_computation\run_batch.py local_matrix_computation\runs\continous_fixed_toplogies\batch_001_sphere_ring_12.json --limit 1
```

Run only jobs whose benchmark name contains a substring:

```powershell
python local_matrix_computation\run_batch.py local_matrix_computation\runs\continous_fixed_toplogies\batch_001_sphere_ring_12.json --only maxDistance
```

Use a specific Python executable:

```powershell
python local_matrix_computation\run_batch.py local_matrix_computation\runs\continous_fixed_toplogies\batch_001_sphere_ring_12.json --python .\.venv\Scripts\python.exe
```

## Running Batch Ranges

Use `run_batch_range.py` when you want several `batch_*.json` files to run one
after another:

```powershell
python local_matrix_computation\run_batch_range.py continous_fixed_toplogies --range 2-4
```

That command runs:

```text
batch_002_sphere_ring_24.json
batch_003_sphere_ring_36.json
batch_004_sphere_torus_12.json
```

Run the first 3 batches from a group:

```powershell
python local_matrix_computation\run_batch_range.py continous_fixed_toplogies --limit-batches 3
```

Run a specific range by explicit path:

```powershell
python local_matrix_computation\run_batch_range.py local_matrix_computation\runs\continous_random_topologies --start 1 --end 5
```

Probe one job from each selected batch:

```powershell
python local_matrix_computation\run_batch_range.py continous_fixed_toplogies --range 1-3 --limit-jobs 1
```

Resume behavior is inherited from `run_batch.py`: without `--force`, finished
jobs with an existing `summary.csv` are skipped. This is the safest default for
overnight runs.

Use `--force` only when you intentionally want to rerun and overwrite:

```powershell
python local_matrix_computation\run_batch_range.py continous_fixed_toplogies --range 1-3 --force
```

The range runner creates logs under:

```text
local_matrix_computation/batch_logs/<group>/
```

Each batch gets its own full console log, plus a small `range_<timestamp>.log`
master log.

## Output Locations

Raw algorithm logs go under:

```text
islands_desync/logs/<date_tag>/<problem_code><variables>/<time_tag> <run_tag>
```

Exported friendly artifacts go under:

```text
local_matrix_computation/results/<group>/<date_tag>/<time_tag>_<benchmark_name>/
```

Each successful run should contain:

```text
summary.csv
summary.json
fitness_all_islands.png
fitness_timeseries.csv
topology_with_fitness.png
topology_metrics.json
param.json
___RESULT.txt
___WINNER.txt
export_manifest.json
```

Check progress for a group:

```powershell
Get-ChildItem -Recurse -Filter summary.csv local_matrix_computation\results\continous_fixed_toplogies | Measure-Object
```

Show the newest summaries:

```powershell
Get-ChildItem -Recurse -Filter summary.csv local_matrix_computation\results | Sort-Object LastWriteTime -Descending | Select-Object -First 10 FullName,LastWriteTime
```

## Aggregating Results

After one or more batches finish, build comparison-ready tables:

```powershell
python local_matrix_computation\aggregate_results.py
```

This scans `local_matrix_computation/results/**/summary.csv` and writes:

```text
local_matrix_computation/analysis/combined_runs.csv
local_matrix_computation/analysis/combined_runs.json
local_matrix_computation/analysis/comparison_groups.csv
local_matrix_computation/analysis/comparison_groups.json
local_matrix_computation/analysis/strategy_ranking.csv
local_matrix_computation/analysis/strategy_convergence_ranking.csv
local_matrix_computation/analysis/topology_ranking.csv
local_matrix_computation/analysis/topology_convergence_ranking.csv
```

Use these files for actual comparisons:

- `combined_runs.csv` - one row per finished run/repeat.
- `comparison_groups.csv` - grouped by problem, topology, island count,
  migration strategy, parameters; includes means/std/min/max across repeats.
- `strategy_ranking.csv` - ranks migration strategies within the same
  problem/topology/island-count setting by `best_final_mean`.
- `strategy_convergence_ranking.csv` - ranks migration strategies by
  `eval_to_90pct_improvement_mean`, i.e. how quickly they reach 90% of their
  own total improvement.
- `topology_ranking.csv` - ranks topologies within the same
  problem/migration/island-count setting by `best_final_mean`.
- `topology_convergence_ranking.csv` - ranks topologies by convergence speed.

Recommended main metrics:

```text
quality:      best_final_mean, mean_final_mean, best_final_std
convergence:  eval_to_50pct_improvement_mean, eval_to_90pct_improvement_mean
budget view:  best_at_25pct_budget_mean, best_at_50pct_budget_mean,
              best_at_75pct_budget_mean, best_at_100pct_budget_mean
stability:    complete_three_repeats, run_count, std columns
```

For minimization problems, lower is better for both final fitness and
`eval_to_*` convergence metrics.

The current output is enough to compare:

```text
function x topology x island_count x migration_strategy
```

using final quality, convergence curves, run-to-run variability, and topology
metrics. For mechanistic debugging of migration internals, keep the raw
`islands_desync/logs/...` directories too; they contain the lower-level per
island JSON files.

## Smoke Aggregation Check

To test the full comparison pipeline without running production batches:

```powershell
python local_matrix_computation\run_batch.py local_matrix_computation\smoke_run\runs\continous_fixed_toplogies\smoke_batch.json --force --limit 1

python local_matrix_computation\aggregate_results.py `
  --results-root local_matrix_computation\smoke_run\results `
  --runs-root local_matrix_computation\smoke_run\runs `
  --output-dir local_matrix_computation\smoke_run\analysis
```

This writes smoke-level aggregate files:

```text
local_matrix_computation/smoke_run/analysis/combined_runs.csv
local_matrix_computation/smoke_run/analysis/comparison_groups.csv
local_matrix_computation/smoke_run/analysis/strategy_ranking.csv
local_matrix_computation/smoke_run/analysis/topology_ranking.csv
```

Validated on 2026-05-13: the smoke aggregation found 2 completed smoke runs
and produced comparison/ranking CSV files successfully.

Important: smoke output is only a pipeline sanity check. It can prove that the
export and aggregation machinery works, but it is not enough for scientific
claims because most smoke groups have `run_count = 1`. Use production batches
with 3 repeats for actual comparisons.

## What Success Looks Like

During a healthy run, the console usually shows:

```text
Started a local Ray instance
step 1 evaluations ...
*** THE END ***
Average result
Best result
Winner island
Saved summary CSV
Saved topology plot
Saved step timeseries CSV
EXPORT_DIR: ...
RUN_DIR: ...
```

The `pkg_resources is deprecated` warning from Ray is noisy but harmless for
these runs.

## What Not To Do

- Do not launch several local batches in parallel unless intentionally stress
  testing Ray.
- Do not run the 1296-job full local matrix as one blind command.
- Do not rename `continous_*`, `descrete_*`, or `*_toplogies` directories.
- Do not paste console lines beginning with `+ C:\...` back into PowerShell;
  those are printed child commands, not commands for the user to type.
- Avoid repeated `Ctrl+C` while Ray is starting actors. If you must stop a run,
  interrupt once, wait for prompt, then run `.\.venv\Scripts\ray.exe stop --force`.
