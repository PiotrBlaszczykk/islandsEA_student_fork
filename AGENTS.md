# AGENTS.md

## Scope
This repository is a research codebase for asynchronous island-model evolutionary computation.  
Treat experiment correctness, comparability, and reproducibility as the primary goal. Do not optimize for refactor cleanliness at the cost of changing semantics.
This document is based primarily on current repository/code inspection and current research context; validate runtime assumptions in the target environment (HPC/local) before high-impact changes.

This repository is not just “parallel GA code”. It is an experimental apparatus for studying:
- asynchronous island execution,
- migration timing / delay effects,
- topology-dependent communication behavior,
- impact of migration strategies (source-side and destination-side) on optimization quality.

Any change that affects migration timing, acceptance, ordering, or logging may affect paper comparability.

---

## Research Context (Current Experimental Intent)

The current research context should be treated as follows:

- The system studies **migration delays** in asynchronous island-model evolutionary algorithms on HPC infrastructure.
- Delay is understood as the difference between:
  - the generation/epoch on the source island when a migrant is sent, and
  - the generation/epoch on the destination island when that migrant is received.
- The sign of this value matters:
  - negative values correspond to “delayed” migrants,
  - positive values correspond to “accelerated” migrants (a source island was evolutionarily ahead of the destination at send time).
- The paper context explicitly suggests that destination-side handling of migrants is research-critical: future operators may reject too-delayed migrants or use only partial information from them. Therefore, migrant acceptance is not merely plumbing; it is part of the experiment design. :contentReference[oaicite:2]{index=2} :contentReference[oaicite:3]{index=3}

Implication for repository work:
- Changes to immigrant acceptance, migrant buffering, receive ordering, queue draining, or topology scheduling are **experiment-semantic** changes.
- Do not change them casually.
- If you do change them, preserve baseline comparability and document what metric behavior is expected to change.

---

## Repository Reality Check (Current Code)

### Top-level layout
- `README.md` (minimal, not operational)
- `islands_desync/` (HPC scripts + Python package root for runtime)
- `islands_desync/islands_desync/` (actual Python source)
  - `start.py` (main Ray/HPC orchestration entrypoint)
  - `geneticAlgorithm/` (GA logic, configs, migrations, utils)
  - `islands/` (island actors, topologies, orchestration)

### Important historical mismatch
Historical notes describe both RabbitMQ and Ray flows. Both code paths exist, but they are not equally maintained:
- **Ray/HPC path appears to be the primary currently used path** (`start.py` + `run_hpc/create_algorithm_hpc.py`), based on current repository structure.
- **RabbitMQ/local path exists but appears legacy/stale in places** (see warnings below).

---

## Execution Paths

## 1) Ray/HPC path (primary, based on current inspection)

### Entrypoint chain
1. `islands_desync/run*.sh` (SLURM script)
2. `python3 -u islands_desync/start.py ...`
3. `islands/core/IslandRunner.py`
4. `islands/core/Computation.py`
5. `geneticAlgorithm/run_hpc/create_algorithm_hpc.py`
6. `geneticAlgorithm/algorithm/genetic_island_algorithm.py`

### `start.py` CLI contract (current)
`start.py` expects **9 positional args**:
1. `island_count`
2. Ray temp dir (or `" "`)
3. `number_of_emigrants`
4. `migration_interval`
5. date tag (`dda`)
6. time tag (`tta`)
7. topology name
8. migrant selection strategy
9. migrant acceptance strategy (`strategy2`)

If arg 9 is missing, the run crashes (`sys.argv[9]` is required).
If arg 2 is `" "`, current code does **not** call `ray.init()` at all; treat `" "` as “skip explicit Ray init”, not as a guaranteed valid fallback mode.

### Working-directory requirement
Run from outer `islands_desync/` directory.  
`create_algorithm_hpc.py` loads config from:
- `./islands_desync/geneticAlgorithm/algorithm/configurations/algorithm_configuration.json`

That relative path assumes CWD is outer `islands_desync/`.

### Verified local run workflow
The active Ray path can be run locally, but the environment needs to match the old dependency stack reasonably closely.

Validated local setup as of May 5, 2026:
- package manager / venv tool: `uv`
- Python: `3.10.20`
- `ray==2.9.3`
- `scikit-learn==1.1.3`
- `setuptools<81` (Ray 2.9.x still imports `pkg_resources`)

Validated local environment creation:
```bash
cd islandsEA/islands_desync
uv venv -c --python 3.10
uv pip install -r islands_desync/islands_desync/geneticAlgorithm/algorithm/requirements.txt ray==2.9.3 scikit-learn==1.1.3 'setuptools<81'
```

Validated local launch command:
```bash
source .venv/bin/activate
cd islandsEA/islands_desync
PYTHONPATH="$PWD" python -u islands_desync/start.py 7 /tmp/islands-ray 5 5 260505 120000 ring random plain
```

Why this exact shape matters:
- `PYTHONPATH="$PWD"` is required because `start.py` imports the package as `islands_desync...`.
- `arg 9` must be present; a baseline non-SAS value like `plain` preserves the default receive-side behavior.
- if the default matplotlib config directory is not writable, add `MPLCONFIGDIR=/tmp/matplotlib` to both run and analysis commands.

Date/time tags must follow the logging contract:
- `dda` becomes the `<date>` directory in `logs/<date>/<prob4><dimension>/...`
- `tta` becomes the leading `<time>` token in the run directory name
- use compact, no-space tags to keep paths predictable
- validated example: `dda=260505`, `tta=120000`
- shell-safe way to generate them:
```bash
dda=$(date +%y%m%d)
tta=$(date +%H%M%S)
```

Expected run directory naming:
- format: `logs/<date>/<prob4><dimension>/<time> <island_count><migrant_code><topology_code>-co<migration_interval>ilu<emigrants>`
- for `7 /tmp/islands-ray 5 5 260505 120000 ring random plain` with the current active `Sphere(200)` setup, the run directory is:
  `logs/260505/Sphe200/120000 7rr-co5ilu5`
- `random` contributes migrant code `r`
- `ring` contributes topology code `r`
- the top-level `start.py` process also emits `logs/iterations_per_second*.json`

Observed local resource caveat:
- `Island`, `Computation`, and `SignalActor` each reserve `num_cpus=1`.
- Practical local island count on a `16`-thread machine is therefore closer to `7` than to `16`.
- `torus` is not a good first local topology because `IslandRunner.py` hardcodes `12 x (island_count // 12)`.

Validated local output from the command above:
- run directory: `logs/260505/Sphe200/120000 7rr-co5ilu5`
- analysis command:
```bash
cd islandsEA/islands_desync
python analyze_migration_delays.py "logs/260505/Sphe200/120000 7rr-co5ilu5"
```

### Current active-path caveat
`IslandRunner.py` currently appears to misassign topologies for islands `1..N-1`:
- island `0` gets `topology[0]`,
- island `1` also gets `topology[0]`,
- subsequent islands are shifted by one,
- the last topology entry is never used.

Treat current topology behavior in live Ray runs as potentially affected by this bug until validated/fixed.

### SLURM script status
- `run144tr-hpc.sh`, `run150rr-hpc.sh` call `start.py` but currently pass only 8 args.
- Several scripts call `start_bm.py`, which is **not present** in this repo.
- `run_smoke_ring.sh` is **not present** in this repository snapshot (it may exist only in local/HPC-side working copies).
- Many scripts contain cluster-specific hardcoded grant/env paths; treat as templates, not ready-to-run defaults.

---

## 2) RabbitMQ/local path (legacy/unverified)

Files present:
- `geneticAlgorithm/docker-compose.yml`
- `geneticAlgorithm/utils/prepare_queues_2.py`
- `geneticAlgorithm/run_algorithm.py`
- `geneticAlgorithm/migrations/queue_migration.py`

Important caveats:
- `queue_migration.py` imports `islands_desync.geneticAlgorithm.migrations.Migration`, but `geneticAlgorithm/migrations/Migration.py` is missing.
- Historical instruction `python run_algorithm.py <island>` does not match current `run_algorithm.py` argv usage (it expects multiple args).
- Treat this path as experimental/legacy unless you validate it end-to-end first.

---

## Experiment-Critical Code Areas (High Risk)
Do not modify casually:
- `geneticAlgorithm/algorithm/genetic_island_algorithm.py`
- `islands/core/*` (actor orchestration and barriers)
- `islands/topologies/*`
- `geneticAlgorithm/utils/distance.py`
- `geneticAlgorithm/run_hpc/create_algorithm_hpc.py`
- `geneticAlgorithm/algorithm/configurations/algorithm_configuration.json`
- `geneticAlgorithm/utils/filename.py` (output naming contract)
- Logging/output generation methods in `genetic_island_algorithm.py`

Additional high-risk areas in current research context:
- any receive-side immigrant queue handling,
- `add_new_individuals` / immigrant acceptance semantics,
- message ordering or batch receive behavior,
- dropping / filtering / partial-use logic for incoming migrants,
- timestamp / epoch capture locations for send vs receive events.

---

## Configuration Semantics

### Primary config file
- `islands_desync/islands_desync/geneticAlgorithm/algorithm/configurations/algorithm_configuration.json`

### The four primary GA parameters
- `number_of_evaluations`
- `number_of_variables`
- `population_size`
- `offspring_population_size`

These are consumed in both Ray/HPC and (legacy) local path.

### Override behavior
In Ray/HPC path (`create_algorithm_hpc.py`):
- `number_of_islands`, `number_of_emigrants`, `migration_interval` are taken from `start.py` args (not from JSON fields of similar names).

In local RabbitMQ path (`run_algorithm.py`):
- island count/migration fields are tied more directly to JSON and CLI assumptions.

Never assume historical example values are authoritative; inspect live config and call path.

---

## Benchmark Selection and Naming Compatibility

### Where the active problem is selected
- Ray/HPC path: `geneticAlgorithm/run_hpc/create_algorithm_hpc.py` (`problem = Sphere(...)` or `Rastrigin(...)`)
- Legacy local path: `geneticAlgorithm/run_algorithm.py` (currently `Rastrigin(...)`, alternatives commented)
- Custom problems: `geneticAlgorithm/utils/myDefProblems.py` (includes `Ackley`, `Schwefel`, `Labs` placeholders/variants)

### Paper-vs-code benchmark mismatch
The paper in the repo root reports experiments with:
- `Rastrigin`
- `200` dimensions
- `population_size = 16`
- `offspring_population_size = 4`
- `migration_interval = 5`
- island counts `50`, `100`, `150`, `200`

The current active Ray/HPC builder defaults to `Sphere(NUMBER_OF_VARIABLES)` in `create_algorithm_hpc.py`, while dimensions and GA sizes come from JSON. Do **not** assume the paper benchmark is the live default configuration.

### Critical compatibility rule
Output paths encode `problem.get_name()[0:4]`.  
Therefore benchmark names must have unique first four characters.

Do not add/rename problems without checking 4-letter collisions with existing and historical experiments.

---

## Migration and Strategy Semantics

### Source-island migrant selection
Implemented in `genetic_island_algorithm.py` (`get_individuals_to_migrate`) using:
- `random`
- `best`
- `worst`
- `maxDistance` (delegates to `geneticAlgorithm/utils/distance.py`)

### Destination-island acceptance
Implemented in `add_new_individuals`; behavior changes when `migrant_acceptation_strategy` contains `"SAS"`.

Migration logic is part of the research apparatus, not plumbing. Any semantic change affects comparability.

### Additional research note on destination-side acceptance
The present research direction makes destination-side acceptance especially important. The paper context indicates:
- delayed migrants can be non-trivially harmful or at least inefficient,
- topology changes delay patterns,
- future work includes dedicated immigration operators that may reject too-delayed migrants or use partial information from them. :contentReference[oaicite:4]{index=4}

Therefore:
- any new acceptance strategy must define what it does with old / highly delayed / accelerated migrants,
- any such strategy must be benchmarked against the baseline receive behavior,
- acceptance changes must be evaluated both for communication behavior and optimization outcome.

---

## Delay Semantics and Measurement Rules

These rules should be treated as the repository-level contract for future changes involving delays.

### Canonical delay definition
For each migrant event, compute:

`delay = source_epoch_at_send - destination_epoch_at_receive`

Store signed values. Do **not** silently convert to absolute values in primary logs.

Interpretation:
- `delay < 0`: delayed migrant,
- `delay > 0`: accelerated migrant,
- `delay == 0`: generation-aligned arrival.

### Required event fields for migrant-level logging
If code is modified in a way that can affect migration timing or acceptance, log or preserve enough information to reconstruct at least:

- `migrant_id` (or stable event identifier)
- `src_island_id`
- `dst_island_id`
- `selection_strategy`
- `acceptance_strategy`
- `topology`
- `send_time`
- `receive_time`
- `send_epoch`
- `receive_epoch`
- `delay`
- `accepted` / `rejected`
- `rejection_reason` (if applicable)
- `fitness_at_send` (if available without semantic disruption)
- `entered_population` (if distinguishable from merely received)

If performance constraints make full per-migrant logging too expensive, state explicitly which fields are omitted and why.

### Do not hide sign information
The paper distinguishes delayed and accelerated arrivals. Do not replace the signed metric with only:
- absolute delay,
- latency in seconds,
- queue age,
unless these are added as supplementary metrics.

Analysis scripts should follow the same sign convention. In particular, any step-based delay reconstruction should use:

`delay_steps = source_iteration - destination_step`

---

## Metrics to Use When Evaluating Delay-Related Changes

If you change migration, topology, receive handling, or immigrant acceptance, evaluate at least the following classes of metrics.

### A. Core delay metrics (minimum required)
- mean delay
- median delay
- min delay
- max delay
- p95 delay
- p99 delay
- proportion of delayed migrants (`delay < 0`)
- proportion of accelerated migrants (`delay > 0`)
- proportion of strongly delayed migrants (thresholded, e.g. `delay < -k`)

The paper reports topology-dependent min/max behavior and characteristic delay patterns; use percentiles in addition for stronger comparison. :contentReference[oaicite:5]{index=5}

### B. Delivery / acceptance metrics
- received migrants count
- accepted migrants count
- rejected migrants count
- undelivered migrants count (if observable)
- acceptance rate
- rejection rate
- rejection reasons histogram

These are particularly important for ring-like cases, where islands may stop receiving fresh migrants after neighboring islands finish work. :contentReference[oaicite:6]{index=6}

### C. Optimization-outcome metrics
- final best fitness
- final average fitness
- best-so-far fitness over time / epoch
- time-to-threshold (if threshold defined)
- per-island final ranking

The paper compares average and final results across topology/strategy combinations; outcome metrics are mandatory, not optional. :contentReference[oaicite:7]{index=7}

### D. Cooperation / desynchronization metrics
- island active start/end time
- common cooperation window length
- percent of time each island works alone
- active-neighbor count over time
- migrants received per unit time / per epoch
- incoming-queue backlog (if queue exists and is measurable)

The paper explicitly analyzes how long islands cooperate simultaneously and links topology to communication crowding and isolated work. :contentReference[oaicite:8]{index=8}

### E. Usefulness metrics for new acceptance strategies (recommended)
If you introduce new destination-side handling, also measure:
- percentage of accepted migrants that actually enter the population,
- survival of accepted migrants after N epochs,
- short-horizon effect on best or average fitness after acceptance,
- usefulness by delay bucket (e.g. `[-inf,-50)`, `[-50,-10)`, `[-10,0)`, `(0,10]`, ...).

These metrics help justify “drop too delayed” policies with evidence rather than intuition.

---

## Visualization Guidance for Delay-Related Experiments

If you add analysis or modify logging, prefer visualizations that preserve comparability with the paper while improving interpretability.

### Strongly recommended figures
1. **Delay time series per island**
   - x-axis: destination epoch or time
   - y-axis: signed delay
   - useful for reproducing characteristic delay-shape patterns

2. **Delay heatmap**
   - x-axis: time / epoch
   - y-axis: island id
   - color: signed delay
   - good for seeing congestion waves and long-lived delayed islands

3. **Island cooperation timeline**
   - horizontal line per island showing active runtime
   - useful for common cooperation window and isolated work

4. **Delay distribution plot**
   - violin / boxplot / ECDF by topology, selection strategy, and acceptance strategy

5. **Optimization progress plot**
   - best-so-far and/or average fitness over time
   - compare baseline vs modified acceptance logic

6. **Delay vs usefulness scatter**
   - delay on x-axis
   - migrant usefulness proxy on y-axis
   - useful when validating threshold-based acceptance or filtering

### Comparison rule
For semantic changes, “before vs after” should be shown under the same:
- benchmark,
- population parameters,
- topology,
- migrant selection strategy,
- island count,
- migration interval,
- emigrant count.

Do not present aggregate charts that hide changed experimental conditions.

---

## Core GA Stack (Confirmed in Code)

The codebase currently uses jMetalPy abstractions/components, including:
- Problems: `Sphere`, `Rastrigin` (`jmetal.problem.singleobjective.unconstrained`)
- Algorithm base: `GeneticAlgorithm`
- Termination: `StoppingByEvaluations`
- Operators seen in code paths/imports: `BinaryTournamentSelection`, `BinaryTournament2Selection`, `PolynomialMutation`, `UniformMutation`, `SBXCrossover`, `SPXCrossover`, `BitFlipMutation`, `RouletteWheelSelection`
- Solution types: `FloatSolution` (and binary solution helper class exists in repository)
- GA abstractions used in typing/base contracts: `Problem`, `Mutation`, `Crossover`, `Selection`, `Evaluator`, `Generator`, `TerminationCriterion`

Not every imported operator is active in the current default run path; many are experimental/commented alternatives.

---

## Topology Semantics and Caveats

### Selection
`start.py` selects topology via `topol` string (`ring`, `torus`, `complete`, `er*`, `ws*`).

### Implementations
- `RingTopology`: current implementation returns `[self, next]` neighbors (non-standard ring; includes self-loop).
- `TorusTopology`: uses 4-neighbor wrapped grid.
- `IslandRunner` hardcodes torus dimensions as `create(12, island_count // 12)`, so torus runs assume `island_count` divisible by 12.

### Known broken/stale topology files
`ERTopology.py`, `WSTopology.py`, `WS1Topology.py`, `WS2Topology.py` reference undefined `topol` variable (commented dict placeholder).  
Using `topol=er`, `ws`, `ws1`, or `ws2` likely fails without fixing these files.

### Hardcoded graph topologies
`ER1/ER2/ER3/ER4` and `WS3/WS4` include large hardcoded adjacency maps.

### Research interpretation of topologies
Paper context suggests:
- `complete` creates the largest communication crowding and delay amplitudes, but can still yield the best optimization results due to more diverse migrant inflow,
- `torus` behaves as an intermediate case,
- `ring` is the most orderly but risks long isolated work and lack of fresh migrants once neighbors finish. :contentReference[oaicite:9]{index=9}

Therefore:
- do not evaluate a delay-reduction change solely by smaller delay values,
- always check whether optimization quality improved, degraded, or merely shifted the trade-off.

---

## Output and Logging Contract (Do Not Break)

Output path builder:
- `geneticAlgorithm/utils/filename.py`
- Format resembles:
  - `logs/<date>/<prob4><dimension>/<time> <island_count><migrant_code><topology_code>-co<migration_interval>ilu<emigrants>`

Examples from actual runs:
- `logs/260407/Sphe30/002459 12rr-co20ilu2`

Where:
- `<prob4>` = first 4 letters of problem name
- migrant code = first letter of selection strategy (`r`, `b`, `m`...)
- topology code = first letter of topology (`r`, `t`, `e`, `w`, `c`...)
- `coX` = migration interval
- `iluY` = number of emigrants

Common generated files:
- `param.json`
- `___RESULT.txt`, `___WINNER.txt`
- `kontrolW<id>Start.ctrl.txt`, `kontrolW<id>End.ctrl.txt`
- `resultsEveryStepW<id>.json`
- `W<id> results jump.json`
- `W<id> set-minOS-srOS-diversity.json`
- `W<id> Imigrants.json`
- `W<id>neighbourRanking.json`
- `W<id>neighbourRankingPercent.json`
- `W<id> czas.json`
- plus top-level `logs/iterations_per_second*.json` from `start.py`

Do not rename/remove/change schema silently. If you must change logging/output semantics, document migration compatibility explicitly.

### Delay-related logging guidance
If adding new metrics, prefer:
- adding new files,
- or adding backward-compatible keys to existing JSON outputs.

Avoid breaking old parsers or historical experiment post-processing without explicit notice.

### Parameter metadata caveat
`param.json` is not a fully trustworthy description of the active Ray/HPC operator stack:
- `genetic_island_algorithm.py` currently reads operator text from `./islands_desync/geneticAlgorithm/run_algorithm.py`,
- but the active Ray/HPC builder is `run_hpc/create_algorithm_hpc.py`.

If operator configuration matters for reproducibility, inspect the active builder directly instead of relying only on `param.json`.

---

## Dependencies and Environment

`algorithm/requirements.txt` is not sufficient for successful Ray/HPC startup by itself.

Likely required extras for the current code path (based on imports and current requirements file contents):
- `ray`
- `scikit-learn` (imported by `utils/tsne.py` at module import time, even if TSNE output flags are false)

If environment setup changes, validate imports before submitting jobs.

If analysis scripts for delay metrics/plots are added, keep them separate from core runtime dependencies where possible.

---

## HPC Dashboard and Plotting Playbook (Ares/SLURM)

This section captures operational knowledge from validated HPC runs and common failures.

### Dashboard prerequisites
- Submit through SLURM (`sbatch ...`), not `sh run_*.sh`. Running directly misses SLURM env vars (`SLURM_JOB_ID`, node list, etc.).
- In interactive/login shell, load module before venv:
  - `module load python/3.10.4-gcccore-11.3.0`
  - `source $HOME/venvs/islands-ray/bin/activate`
- If Ray starts but `http://<head>:8265` is refused, install dashboard extras:
  - `pip install "ray[default]==2.54.1"`
  - then verify: `python -c "import ray, aiohttp, prometheus_client; print(ray.__version__)"`

### Dashboard quick workflow
1. Submit job (optional keep-alive if wrapper supports it):
   - `sbatch --export=ALL,KEEP_DASHBOARD_SECONDS=600 <script>.sh`
2. Check if still running:
   - `squeue -j <JOBID>`
   - `sacct -j <JOBID> --format=JobID,State,ExitCode,Elapsed,NodeList -X`
3. Get head node from SLURM log:
   - `HEAD=$(grep -m1 "Starting HEAD at" slurm-<JOBID>.out | awk '{print $4}')`
4. Validate dashboard from login node:
   - `curl -sS -m 5 http://$HEAD:8265/api/version`
5. From **laptop/local terminal**, open SSH tunnel:
   - `ssh -N -L 18265:$HEAD:8265 <user>@login01.ares.cyfronet.pl`
6. Open browser:
   - `http://localhost:18265`

### Dashboard caveats
- Ray UI `Overview/Jobs/Actors` may work while `Metrics` look empty; this is expected without Prometheus/Grafana integration.
- If dashboard still fails, inspect Ray logs on head node:
  - `/tmp/$USER/<JOBID>/session_latest/logs/dashboard.log`
  - `/tmp/$USER/<JOBID>/session_latest/logs/dashboard.err`

### Quick plot from experiment logs
For per-island fitness curves, read `resultsEveryStepW*.json` in run directory and generate PNG with matplotlib.

Required pattern:
1. Set and **export** run directory variable (spaces are common in path names):
   - `export RUN_DIR="logs/<date>/<prob4><dim>/<time> <tag>"`
2. Run plotting snippet (inline Python or helper script) that saves:
   - `$RUN_DIR/fitness_all_islands.png`

### File transfer gotchas
- `scp ... .` copies into the current shell location. If run on Ares, file stays on Ares.
- To download to laptop, run `scp` from laptop terminal.
- With space-heavy paths, easiest method:
  1. on cluster: `cp "$RUN_DIR/fitness_all_islands.png" "$HOME/fitness_all_islands.png"`
  2. on laptop: `scp <user>@login01.ares.cyfronet.pl:~/fitness_all_islands.png .`

---

## Before Making Changes
1. Identify which execution path is affected (Ray/HPC vs legacy RabbitMQ/local).
2. Trace real call graph from entrypoint before editing.
3. Check whether change touches high-risk experiment-critical areas.
4. Inspect config consumption in code (do not trust historical docs blindly).
5. Verify topology/problem/logging implications.
6. Note any mismatch between docs/scripts and live code.
7. For delay-related changes, state explicitly:
   - which delay metric is expected to change,
   - whether optimization quality is expected to change,
   - whether comparability to prior runs is preserved.

---

## After Making Changes
1. `git status`
2. `git diff --stat`
3. `git diff` (manual review for semantic drift)
4. Run smallest relevant validation:
   - Import-level validation for changed modules
   - For orchestration/migration/topology changes: at least one minimal run that reaches island `step` loop
5. If config semantics changed, verify values are actually read in active path.
6. If logging changed, verify expected output files are still produced.
7. If migration/acceptance changed, verify new delay metrics are actually emitted and interpretable.
8. State clearly what was validated and what was not (especially HPC paths).

---

## Never Do This
- Do not perform drive-by refactors in core experimental code.
- Do not remove "noisy" logs/output files without explicit request.
- Do not change benchmark naming conventions casually.
- Do not silently alter parameter meaning or units.
- Do not modify migration/topology semantics without noting experiment comparability impact.
- Do not replace signed delay metrics with only absolute or aggregated values.
- Do not claim success if only static edits were done and no minimal run/import validation was performed.

---

## Safe-ish Extension Points

Lower-risk additions:
- Add new benchmark problems in `geneticAlgorithm/utils/` (ensure unique first 4 letters in `get_name()`).
- Add analysis/visualization scripts that consume existing logs.
- Add convenience HPC wrappers/scripts (without changing core algorithm semantics).
- Add backward-compatible delay metrics exporters and postprocessing scripts.

Higher-risk additions:
- New migration strategies (source or destination acceptance) in core loop.
- Topology behavior changes.
- Output naming/log schema changes.
- Changes to orchestration barriers/signaling (`SignalActor`, migration pipeline).
- Receive-side queue ordering, filtering, or delayed-migrant dropping logic.

---

## Recommended Validation Matrix for Delay/Acceptance Changes

When changing destination-side acceptance or migration timing behavior, prefer at least:

- topologies: `ring`, `torus`, `complete`
- source strategies: `best`, `random`, `maxDistance`
- same benchmark and GA core parameters as baseline
- multiple runs per setting (do not rely on single-run anecdotal results)

Minimum reporting set:
- final best fitness,
- final average fitness,
- median/p95 delay,
- min/max delay,
- acceptance/drop rate,
- common cooperation window length,
- one representative delay visualization,
- one optimization-progress visualization.

---

## Historical Notes (Use as Hints, Not Truth)
- Old notes mention local RabbitMQ-first workflow and `run_algorithm.py` manual runs.
- Current repository includes those artifacts, but they may be partially stale.
- If you need that path, validate it explicitly before relying on it.

---

## Verified Historical Paths (Current Repository)
- Main evolutionary loop: `islands_desync/islands_desync/geneticAlgorithm/algorithm/genetic_island_algorithm.py`
- Example HPC script: `islands_desync/run144tr-hpc.sh`
- Base configuration: `islands_desync/islands_desync/geneticAlgorithm/algorithm/configurations/algorithm_configuration.json`
- Legacy/local problem selection path: `islands_desync/islands_desync/geneticAlgorithm/run_algorithm.py`
- Custom problems: `islands_desync/islands_desync/geneticAlgorithm/utils/myDefProblems.py`
- Migrant source strategy helpers: `islands_desync/islands_desync/geneticAlgorithm/utils/distance.py`

These paths exist, but not all represent equally healthy/maintained runtime paths.
