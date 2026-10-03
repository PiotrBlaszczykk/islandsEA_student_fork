# CSV database for completed runs

`build_results_database.py` reads the portable `run_*.tar.gz` bundles directly.
It does not unpack or copy raw runs into this repository. The default local
output, `analysis_database/`, is ignored by Git.

The layout separates rebuildable processing data from report output:

```text
analysis_database/
  database_manifest.json, SCHEMA.md, topologies/
  .processing/          # all CSV/CSV.GZ tables and per-run shards
outputs/                 # all default PNGs, tables and report metadata
```

`.processing/` may be removed when no further reports or incremental updates
are needed. Recreating it requires ingesting the source archives again. Report
commands never write PNG files under `analysis_database/`.

Build the database from the current campaign:

```bash
python analysis/build_results_database.py /mnt/d/island_ea/torus_best --workers 4
```

When `torus_random` appears next to `torus_best`, append only its new runs:

```bash
python analysis/build_results_database.py /mnt/d/island_ea/torus_random
```

It is also safe to point the script at the common parent repeatedly:

```bash
python analysis/build_results_database.py /mnt/d/island_ea --workers 4
```

Already ingested archives are identified by SHA-256 and skipped. Each run is
published atomically as a separate shard, then the combined per-run and
per-configuration CSVs are rebuilt. Running the same command again does not
duplicate rows.
Do not run two ingester processes against the same output directory at once.

## Exact topology archive

Newly ingested runs automatically add their complete `results/topology.json`
to the analysis database. To add topologies to an already built database
without rebuilding its large convergence tables, run:

```bash
./.venv/bin/python analysis/build_results_database.py /mnt/d/island_ea \
  --output analysis_database \
  --collect-topologies-only \
  --workers 4
```

The source directory currently present on this machine is `/mnt/d/island_ea`
(singular `island_ea`). The collector first reads the early `metadata.json`
from every archive, groups runs by topology name, parameters and exact
adjacency SHA-256, and then reads one full representative archive per distinct
variant. This avoids decompressing all large archives merely to recover the
same fixed graph.

Full payloads are stored once as
`topologies/<topology_payload_sha256>.json`.
`.processing/topologies.csv` inventories the unique payloads, while
`.processing/topology_runs.csv` maps every run to its exact payload and
adjacency hash. Consequently, if a future topology is randomized and its
ordered adjacency differs, it is retained as a separate content-addressed
file even when the topology name is unchanged.

`--workers` controls in-process thread pools. Directory subtrees are searched
concurrently; archive validation and both streaming passes then run concurrently
for independent runs. Publication into
`.processing/runs/<run_id>/` is protected by a lock and remains atomic. After ingestion,
the four combined tables and three configuration tables are rebuilt in
parallel, but each reads run shards in deterministic sorted order. Therefore
`--workers 1` and `--workers 4` produce byte-identical CSV tables. The default
is `min(4, available CPUs)`; use `--workers 1` for sequential diagnostics or a
smaller value if the source disk is saturated. This is multithreading inside
one process, not permission to run multiple updater processes concurrently.

After an intentional interruption, compact views of the already completed
shards can be rebuilt without reading source archives:

```bash
python analysis/build_results_database.py --output analysis_database \
  --rebuild-views-only --workers 4
```

The processing workspace contains:

- `.processing/runs.csv`: final best, worst, mean and median over all islands; convergence
  speed of the run-wide best result; scientific conditions and provenance;
- `.processing/islands.csv`: final result/rank and convergence speed for every island;
- `.processing/run_convergence.csv`: convergence envelope per run;
- `.processing/delay_summary.csv`: signed-delay distributions for top/bottom islands;
- `.processing/configuration_summary.csv`: final outcomes and convergence-speed metrics
  grouped by identical scientific configuration and aggregated over repeats;
- `.processing/configuration_convergence.csv`: pointwise repeat-aggregate curves
  over repeats of each configuration;
- `.processing/configuration_delay_summary.csv`: delay metrics for each group,
  first computed per repeat and then summarized over repeats;
- `topologies/<sha256>.json`: deduplicated exact topology payloads, including
  ordered adjacency lists and graph metrics;
- `.processing/topologies.csv` and `.processing/topology_runs.csv`: exact
  run-to-topology mapping;
- `.processing/runs/<run_id>/island_convergence.csv.gz`: full histories;
- `.processing/runs/<run_id>/top_bottom_delay_events.csv.gz`: signed delays,
  including end-of-run censored records with empty delay values.

Archive extraction uses only the Python standard library. Plotting additionally
uses NumPy, Matplotlib and scikit-learn from the project `.venv`. See the
generated `analysis_database/SCHEMA.md` for definitions of convergence speed
and nulls.

The `configuration_*.csv` tables are the primary input for final comparative
plots. The per-run tables remain available for auditing individual trials.

## Simple repeat-averaged fitness tables

Generate one compact table for every benchmark:

```bash
./.venv/bin/python analysis/build_results_database.py \
  --output analysis_database \
  --export-fitness-table
```

The default files are
`outputs/<benchmark>/fitness_summary.csv`. Select another root
directory with `--fitness-table-output PATH`. Each table has one row per
topology/selection/acceptance configuration and no `run_id`, `job_id`,
`experiment_key` or other run identifiers. `repeats_averaged` records how many
runs contributed; for the complete current database it is 3 in every row.
Fitness plot jobs keep these summary tables and add only PNG files; they do not
create fitness manifests, comparison-context tables, plot-series CSVs or
README files.
The mean columns are:

- `mean_final_fitness`;
- `mean_best_fitness_at_25pct_evaluations`, `...50pct...`, `...75pct...` and
  `...100pct...`;
- `mean_evaluations_to_50pct_observed_improvement` and
  `mean_evaluations_to_90pct_observed_improvement`.

The value is first computed independently for each run and then averaged over
its repeats, so configurations are never mixed. Run-level fitness is the
global best-so-far across all islands. For budget fraction `q`, the exporter
takes the last recorded point whose per-island evaluation counter is not
greater than `q * evaluations_budget_per_island`; it never uses a later result.
In complete current runs the requested quarter points are recorded exactly.

The improvement thresholds use the run's observed initial-to-final change:

```text
progress(e) = (initial_best - best_so_far(e)) / (initial_best - final_best)
```

for minimization, with the direction reversed for maximization. Each run's
evaluation count is the first per-island counter where progress reaches 50%
or 90%, including the initial-population evaluations; the table stores the
mean of those three counts. A mean is empty when the metric is unavailable in
all repeats, and partially missing repeat data is rejected rather than silently
averaged.

## Separate delay-pattern images

Generate the aggregate over all benchmarks: 8 most frequent patterns among
the final 10 best islands and 8 among the final 10 worst islands:

```bash
./.venv/bin/python analysis/build_results_database.py \
  --output analysis_database --plot-delay-patterns
```

This creates separate files, not a montage:

```text
outputs/delay_plots/top_10/pattern_01.png ... pattern_08.png
outputs/delay_plots/top_10/pca_clusters.png
outputs/delay_plots/bottom_10/pattern_01.png ... pattern_08.png
outputs/delay_plots/bottom_10/pca_clusters.png
```

Restrict clustering and rendering to one benchmark with:

```bash
./.venv/bin/python analysis/build_results_database.py \
  --output analysis_database \
  --plot-delay-patterns \
  --pattern-benchmark b01_labs_binary
```

The filtered result is written under
`outputs/b01_labs_binary/`, alongside that benchmark's fitness outputs. Only that
benchmark's run shards are read. `--delay-pattern-benchmark` is accepted as a
more explicit alias.

Restrict the same report to one database run with:

```bash
./.venv/bin/python analysis/build_results_database.py \
  --output analysis_database \
  --plot-delay-patterns \
  --pattern-run RUN_ID
```

The default destination is `outputs/runs/<RUN_ID>/`. An explicit
`--pattern-output PATH` overrides it. `--pattern-run` and
`--pattern-benchmark` are mutually exclusive.

Generate a separate filtered report automatically for every benchmark with:

```bash
./.venv/bin/python analysis/build_results_database.py \
  --output analysis_database \
  --plot-delay-patterns-all \
  --workers 4
```

This discovers benchmark names from the database and writes each report to
`outputs/<benchmark>/`; curves from different benchmarks are not clustered
together. Benchmarks are processed concurrently using `--workers`; use
`--workers 1` for the sequential mode. Matplotlib figure creation is protected
because Matplotlib has process-global state, while loading delay shards,
feature extraction and clustering run concurrently. In this mode, an explicit
`--pattern-output PATH` selects the parent directory, so reports go to
`PATH/<benchmark>/`. With
`--plot-delay-patterns`, the same option still selects the exact destination
directory for the single filtered report or the all-benchmark aggregate.

Delay publication writes only PNG files under `top_*` and `bottom_*`; it
preserves the benchmark's fitness summary and fitness plot directories. It also
removes legacy `cluster_summary.csv`, `curve_assignments.csv`,
`configuration_pattern_frequency.csv` and `pattern_manifest.json` files left by
older generator versions.

Each group also contains `pca_clusters.png`. It projects the exact normalized
feature vectors supplied to K-Means onto their first two PCA components. Each
point is one island-run delay curve, colors are the resulting K-Means clusters,
and an `X` marks the observed medoid used as the cluster's representative.
The PCA projection is only a visualization and does not change clustering.

The method first forms 12 reproducible shape clusters in each group (matching
the A-L candidate count in paper Fig. 4), then renders the observed medoid from
each of the 8 largest clusters. Curves use normalized epoch bins and signed
delay mean/std/min/max plus coverage for clustering; the PNG itself shows the
raw processed delays against recipient epoch and a smoothed binned mean.

Mathematically, for curve `i`, normalized epoch bin `k` and its processed
delays `M_ik`, the clustering channels are

```text
mu_ik = (1/|M_ik|) * sum_{d in M_ik} d
sigma_ik = sqrt((1/|M_ik|) * sum_{d in M_ik} (d-mu_ik)^2)
min_ik, max_ik, coverage_ik = 1[|M_ik| > 0].
```

Missing bins are linearly interpolated and delay channels are smoothed. With
`s_i` equal to their joint 90th percentile absolute amplitude, the feature is
the concatenation of `mu/s_i`, `sigma/s_i`, `min/s_i`, `max/s_i` and coverage.
KMeans minimizes the within-cluster squared Euclidean distance

```text
sum_l sum_{i in C_l} ||z_i - center_l||^2.
```

Cluster frequency is `|C_l| / |G|` in top/bottom group `G`; the shown curve is
the actual observed member nearest the cluster center. For configuration `c`,
`mean_curves_per_repeat = n_cl / R_c` and
`configuration_group_fraction = n_cl / n_c`.

## Repeat-aggregated fitness comparison plots

For one benchmark, generate both useful layouts:

```bash
./.venv/bin/python analysis/build_results_database.py \
  --output analysis_database \
  --plot-fitness r01_elliptic \
  --fitness-group-by both
```

- `by_strategy/strategy_best.png`, etc.: one PNG per available migration
  strategy, with one line per topology (up to the five study topologies);
- `by_topology/topology_torus.png`, etc.: one PNG per available topology, with
  one line per strategy (up to the three study strategies).

Use `--fitness-group-by strategy` or `--fitness-group-by topology` to generate
only one split layout. To put every available pair on one plot, use:

```bash
./.venv/bin/python analysis/build_results_database.py \
  --output analysis_database \
  --plot-fitness r01_elliptic \
  --fitness-group-by combined
```

This writes `combined/all_topology_strategy_configurations.png`. Its lines are
labelled `topology / strategy`, for example `torus / best`, `torus / random`
and `complete / best`. `combined` means one comparison chart, not averaging
different topology/strategy pairs together.

Generate the selected layout for every benchmark in the database with one
command:

```bash
./.venv/bin/python analysis/build_results_database.py \
  --output analysis_database \
  --plot-fitness-all \
  --fitness-group-by combined
```

This reads `.processing/configuration_convergence.csv` once and writes one
directory per benchmark under `outputs/`. With
`--fitness-output PATH`, `PATH` is the parent directory for those benchmark
directories. All plot titles, labels and legends are in English.

To additionally copy only the PNG files to a second tree, add:

```bash
  --fitness-images-output another_png_directory
```

The optional second tree always uses
`<benchmark>/<layout>/<plot-name>.png` and contains no CSV tables, README files
or manifests. The primary report remains under `outputs/`.

Each line in every layout is the pointwise arithmetic mean of
`global_best_so_far` over repeats of exactly the same configuration. The band
is plus/minus the population standard deviation over those repeats. If the
database contains incompatible GA settings for the same benchmark, they are
placed in separate `context_<id>/` folders rather than averaged together.

## Mathematical definitions of the metrics

Let `N` be the island count, `e_0 < ... < e_T` the evaluation counts per
island, and `b_i(e_j)` the recorded `best_so_far` of island `i`. All current
study problems are minimized. Maximization uses the reverse ordering and
reverse improvement difference from `objective_direction`.

### Final fitness

For `f_i = b_i(e_T)` (verified against `final_solution.json`):

```text
best   = min_i f_i                    worst = max_i f_i
mean   = (1/N) * sum_i f_i            median = median_i(f_i)
std    = sqrt((1/N) * sum_i (f_i - mean)^2)
```

Final rank is ascending by `(f_i, island_id)`. `top_10` means ranks 1..10;
`bottom_10` means ranks `N-9..N`. `fitness_tie_size` counts islands with the
same stored final value.

### Aggregation over repeats

The scientific configuration key includes benchmark/dimension, objective, GA
and migration parameters, exact topology, selection and acceptance strategies,
and metrics profile. It excludes run ID, repeat, seed, job ID and campaign
folder. For scalar metric `y_r` in `R` repeats:

```text
mean_c(y)   = (1/R) * sum_{r=1..R} y_r
median_c(y) = median_r(y_r)
std_c(y)    = sqrt((1/R) * sum_{r=1..R} (y_r - mean_c(y))^2)
```

The configuration tables also store repeat-wise min/max and the number of
available non-empty repeats. For the fitness curve the same aggregation is
performed independently at every evaluation point `e_j`:

```text
mean_c[B(e_j)] = (1/R) * sum_{r=1..R} B_r(e_j).
```

For a top/bottom island group `G` within one run, an event-pooled delay mean is

```text
mu_G = [sum_{i in G} n_i * mu_i] / [sum_{i in G} n_i],
```

where `n_i` is the processed-delay count of island `i`. Event fractions use
the analogous sum of category counts. Fields prefixed `equal_island_` instead
give every island equal weight, for example
`(1/|G|) * sum_i mu_i`. These per-run group values are then summarized over
repeats with the same formulas above.

### Convergence and convergence speed

The best result in a run at evaluation `e_j` is

```text
B(e_j) = min_i b_i(e_j).
```

The light `run_convergence.csv` additionally stores mean, median and worst
(`max`) over all `b_i(e_j)`. Full island curves remain in the per-run gzip CSV.

For an island curve or the run-wide curve, write it as `x(e)`. Its observed
improvement and progress are

```text
Delta = x(e_0) - x(e_T)
p(e_j) = (x(e_0) - x(e_j)) / Delta, clipped to [0,1].
```

For `q in {0.10, 0.50, 0.90, 0.95, 1.00}`:

```text
e_q = min { e_j : p(e_j) >= q }.
```

The implementation uses `q=1-10^-12` for the final threshold. The normalized
trapezoidal progress area is

```text
AUC = [1 / (e_T - e_0)]
      * sum_{j=1..T} ((p(e_{j-1}) + p(e_j))/2) * (e_j - e_{j-1}).
```

`AUC in [0,1]`; higher means the observed improvement happened earlier. With
`eps=10^-12 * max(|x(e_0)|, |x(e_T)|, 1)`, `strict_improvement_count` counts
adjacent decreases larger than `eps`. If `Delta <= eps`, AUC and thresholds are
empty. The evaluation axis is per island.

### Signed delays and censoring

For processed migrant `m`:

```text
d_m = source_step_m - process_step_m.
```

- `d_m < 0`: delayed/stale;
- `d_m = 0`: aligned;
- `d_m > 0`: accelerated;
- `d_m < -k`: strongly delayed, with default `k=10`.

A terminal `processed=false` record is censored/backlog. It is retained with an
empty delay and excluded from delay statistics, so

```text
process_event_count = processed_event_count + censored_event_count.
```

For `n` processed delays, category fractions are counts divided by `n`.
The mean is `(1/n) sum_m d_m`. Percentile `p` is linearly interpolated at
`h=(n-1)p`: if `a=floor(h)`, `b=ceil(h)` and sorted delays are `d_(j)`, then

```text
Q(p) = d_(a) * (1-(h-a)) + d_(b) * (h-a).
```

The CSV stores min, p05, p25, mean, median, p75, p95, p99, max and all signed
category counts/fractions. Empty values retain source `null`; they are never
silently replaced with zero.
