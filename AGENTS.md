# AGENTS.md

## Active study and source precedence (2026-09-16)

This checkout targets **Ares CPU**, branch `summer_benchmarks_ares`. The Athena GPU checkout is a separate sibling repository.

Read the updated [research scope](../../zakres_badan.md) and the repository's
[STUDY_144.md](STUDY_144.md) first. The workspace Markdown preserves the PDF's
tasks/hypotheses and incorporates the later supervisor email. A standalone
cluster checkout may not contain the workspace file; STUDY_144.md retains
the operational contract inside each repo.

The email supersedes the PDF's old 150-200 island range and selects the graph
instances. Do not restore old counts or substitute freshly generated graphs.
Historical paper settings and ares-info/athena-info debugging snapshots do
not override current study instructions; preserve their measured job records.

### Fixed experiment and selected instances

| Setting | Current study |
|---|---|
| Islands | **144 for every topology/repeat/platform** |
| Migration interval / migrant group | **5 / 5** |
| Evaluations | **8000 per island**, 1,152,000 per full run |
| Population / offspring | **16 / 4** |
| Dimension | Problem-dependent; e.g. Sphere D=200. Do not change D to 144. |
| Topologies | torus 12x12, complete, selected ER4, selected WS3, supplied BA |
| Selection strategies | best, random, maxDistance |
| Acceptance baseline | plain; extra acceptance experiments are optional |
| Benchmarks / repeats | 40 / 3, giving 5 x 3 x 40 x 3 = 1800 runs |

- Migration interval currently means evaluation-counter difference, not generations. Preserve that semantic distinction.
- The suite contains 30 continuous CEC2014 functions and 10 separate binary problems. The binary functions are not part of official CEC2014. Official continuous instances use D=10/30/50/100; D=200 is the labelled IslandsEA extension.
- Graph originals: workspace `../../grafy/ER4Topology.py`, `WS3Topology.py`, `BA grapf - 144 nodes.txt`. Runtime copies: `islands_desync/islands_desync/islands/topologies/data/{er4,ws3,ba}.json`. These committed copies suffice on the cluster; no runtime download or regeneration.
- **WS3**: 144 nodes, 1803 undirected edges; source label parameters dim=2, lat=12, nei=3, probab=0.003181, scenario=2.
- **BA**: 144 nodes, 3855 undirected edges; supplied m0=30, m=30.
- **ER4 BLOCKER**: supplied 150 nodes (0-149), 728 directed adjacency entries including 6 self-loops; label ERt3.2, probab unknown/null. Its 144-island run must stay blocked until a corrected attachment or an explicit methodological decision arrives. No truncation, symmetrization, loop removal or replacement graph has been approved.
- Preserve exact adjacency, node IDs, neighbour order, source filename/hash and adjacency hash across repeats and CPU/GPU. Never infer ER probab from density.
- Main matrix excludes ring and worst selection. Ring and small-island runs require `--diagnostic` and are separate from research data. The historical ring hypothesis does not add a sixth topology to the matrix.
- Research tasks: compare PEA results, analyze signed-delay patterns for the **10 best and 10 worst islands per trial**, describe contributions and preliminary results. The original deadline is the end of September.
- Hypotheses concern smaller delay amplitudes and better/non-degraded optimization for selected ER/WS/BA versus complete/torus. They are not measured conclusions of the current campaign.

### Runtime, metrics and readiness

- Preserve results of **all 144 islands**, `param.json`, graph parameters, exact `topology.json`, `topology.png` and complete `research-v1-full-buffered` telemetry. Keep the existing signed-delay, queue, acceptance, survival, fitness and runtime metric definitions.
- Same CPU/GPU scientific contract means same objective/instance, graph, algorithm settings, seed policy and metric schema. Hardware timing and asynchronous ordering may change delays and final trajectories; do not promise bitwise-identical final GA results across devices.
- Named `run_benchmark.py` defaults to/requires 144 for study runs, validates graphs before Ray and records graph provenance. Ares submitters also validate before sbatch. The JSON defaults are now 144 islands and interval 5; active runtime overrides remain authoritative.
- Ares: `submit_ares_144.sh`, branch `summer_benchmarks_ares`, 7 x 48 = 336 allocated CPUs, 335 advertised Ray CPUs, 289 required Ray CPUs plus driver (minimum 290 physical CPUs). Six nodes with 48 CPUs each are insufficient.
- Pilot: `pilot_run/pilot_spec.json`, F1/r01 D=200, torus 12x12, 144 islands, best/plain, repeats 1-3. Full pipeline ceiling 561.5 CPUh; `launch_pilot.sh --confirm-144-and-562-cpuh`. No CONFIRM_TORUS_200 methodology gate remains. Keep clean/pinned commit, canary verification, SCRATCH, finalizer and no-retry guards.
- Old `*_ares_200.sh`, `run*-hpc.sh`, `run_delay_experiment.sh`, `run_local_venv_plgrid.sh` and `submit_all_topologies.sh` are retired/fail closed. Do not use them as campaign templates. Job paths use ISLANDS_PROJECT_DIR/SLURM_SUBMIT_DIR, not the SLURM spool copy's BASH_SOURCE.
- Athena has explicit NumPy/CuPy benchmark backends but **no integrated full GPU island runner yet**. GPU validation batches include 144/288/576/864/1152/1728/2304; theoretical initial population totals 2304, offspring per ideal global wave 576. These totals do not authorize adding a synchronization barrier. Do not submit the Ares CPU profile on Athena.
- Current local evidence: `../../artifacts/study144/validation.json`, 33 tests per repo (66 total), real CLI dry-runs and exact attachment checks; `../../artifacts/study144/parity.json`, 170 instances / 5946 inputs per comparison, no unexpected source differences. This is CPU evidence, not a 144-island HPC run or validation of the complete 40-function backend on A100.
- Historical small positional `start.py` commands below are archival. Use the current named launcher with `--diagnostic` for CPU smoke tests. The September16 update changes documentation only; it does not itself submit jobs or certify new GPU results.

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

Paper context: the local `Delays_in_computing_with_Parallel_metaheuristics_on_HPC_infrastructure-1.pdf` and `raport.md`. Current task requirements are in the updated research scope linked above.

The current research context should be treated as follows:

- The system studies **migration delays** in asynchronous island-model evolutionary algorithms on HPC infrastructure.
- Delay is understood as the difference between:
  - the generation/epoch on the source island when a migrant is sent, and
  - the generation/epoch on the destination island when that migrant is received.
- The sign of this value matters:
  - negative values correspond to “delayed” migrants,
  - positive values correspond to “accelerated” migrants (a source island was evolutionarily ahead of the destination at send time).
- The paper context explicitly suggests that destination-side handling of migrants is research-critical: future operators may reject too-delayed migrants or use only partial information from them. Therefore, migrant acceptance is not merely plumbing; it is part of the experiment design.

Implication for repository work:
- Changes to immigrant acceptance, migrant buffering, receive ordering, queue draining, or topology scheduling are **experiment-semantic** changes.
- Do not change them casually.
- If you do change them, preserve baseline comparability and document what metric behavior is expected to change.

---

## Repository Reality Check (Current Code)

### Top-level layout
- `README.md`, `STUDY_144.md`, `hpc_benchmarks/README.md`, `pilot_run/README.md` (current study and operational entry points)
- `islands_desync/` (HPC scripts + Python package root for runtime)
- `islands_desync/islands_desync/` (actual Python source)
  - `start.py` (legacy positional Ray entrypoint; maintained named entrypoint: `hpc_benchmarks/run_benchmark.py`)
  - `geneticAlgorithm/` (GA logic, configs, migrations, utils)
  - `islands/` (island actors, topologies, orchestration)

### Important historical mismatch
Historical notes describe both RabbitMQ and Ray flows. Both code paths exist, but they are not equally maintained:
- **Named Ray/HPC path is maintained**: `hpc_benchmarks/run_benchmark.py` -> `IslandRunner` -> `run_hpc/create_algorithm_hpc.py`. Legacy `start.py` reaches the same builder but does not replace the named launcher's complete provenance contract.
- **RabbitMQ/local path exists but appears legacy/stale in places** (see warnings below).

---

## Execution Paths

### Named benchmark launcher (added September 12, 2026)

- Operational instructions: `hpc_benchmarks/README.md`.
- `hpc_benchmarks/run_ares.sh` starts Ray head/workers inside one SLURM allocation and invokes `run_benchmark.py`, which calls the existing `IslandRunner` directly. Legacy `start.py` remains available.
- `hpc_benchmarks/validate_ares.sh` runs selected-topology tests and pilot/metrics tests, then benchmark/integration validation on a compute node without a Ray cluster. Old reports describing only 17 benchmark tests predate these graph checks; require every stage to pass.
- `run_hpc/benchmark_configuration.py` reads the existing JSON and optional `ISLANDS_CONFIG`, `ISLANDS_PROBLEM`, `ISLANDS_NUMBER_OF_VARIABLES`, `ISLANDS_NUMBER_OF_EVALUATIONS`, `ISLANDS_POPULATION_SIZE`, `ISLANDS_OFFSPRING_POPULATION_SIZE`. Validate a positive whole number of offspring batches; never silently round the budget.
- Refined suite: 30 continuous CEC functions (official D=10/30/50/100, explicitly custom IslandsEA D=200) and the same 10 binary functions from help. Fixed data and golden references are committed with the package; no per-worker generation/downloads. Runtime mathematical modules are identical to help at port time.
- Binary operators are BitFlip(1/bits) and SPX; continuous operators remain MyUniformMutation(1/D, 10) and SwitchCrossover. `active_operators` is authoritative; the old `param.json` text field `operators` remains for compatibility.
- BinarySolution stores a nested bit vector. `utils/decision_variables.py` flattens it for distance, diversity and population logging; logged problem size is number of bits. `maxDistance` sums squared bit differences (Hamming), keeping existing selection and tie order. Continuous distance arithmetic is preserved.
- `--seed` and `--repeat` give seed `seed + (repeat-1)*1000000 + island_id`; these seeds do not change benchmark instances or guarantee deterministic asynchronous ordering. Old launches without `ISLANDS_SEED` preserve their RNG policy.
- Existing actor reservations require `2*N+1` logical Ray CPUs; the SLURM wrapper reserves one additional head CPU for the driver. BLAS/OMP threads are restricted to 1. Code, instance, configuration, Python and dependency versions are checked on every node before the timed run.
- Canary, gate, full array and finalizer are pinned to the same clean Git commit. Changing or dirtying the shared checkout while they are queued makes the affected stage fail closed.
- **Ares storage contract (September 13, 2026):** source `hpc_benchmarks/ares_storage.sh` and call `islandsea_configure_storage` in submitters and jobs. With `$SCRATCH` available, generated data lives under `$SCRATCH/islandsEA/`: raw runs in `results/runs`, compact audit in `results/audit`, pilot archives/summaries in `results/pilot_runs`, SLURM logs in `logs/slurm`, failure-only Ray logs in `logs/ray_failures`, and reserved roots in `checkpoints` and `tmp`. Repo/config and the existing venv remain in HOME. The fallback is `$HOME/islandsEA` with a warning. Do not reintroduce output under the repo, `~/artifacts`, or relative `logs/` in an Ares launcher. Submit via `pilot_run/submit_*.sh`, `hpc_benchmarks/submit_*.sh`, or `smoke_run/submit_smoke.sh`, because `#SBATCH` does not expand shell variables; `/tmp` in job headers is only a safe non-HOME fallback.
- Every named benchmark run writes `run_metadata.json` as well as `experiment_manifest.json`. `run_metadata.json` is the aggregation contract: it records a unique `run_id`, stable SHA-256 `experiment_key`, all benchmark/GA/migration/topology settings, repeat and seed policy, topology hash, resources/SLURM IDs, Git/code/dependency provenance and resolved storage/output paths. The pilot validator must reject missing or inconsistent metadata.
- The pilot requires metrics profile `research-v1-full-buffered`. Each island writes `metrics/island_NNN/{migration_events,queue_fetches,fitness_history}.jsonl.gz`, `final_solution.json`, `runtime.json` and `summary.json`; the root `metrics/data_contract.json` defines the schema. Migration records share `(run_id,event_id)` across send/process and retain enqueue/dequeue timestamps, queue depth/residence, pre-filter decision, replacement survival and a 25-step survival observation. Fitness includes the initial population and every step on evaluation/time axes. Telemetry stays in actor memory during optimization and is compressed only after the finish barrier; never replace it with per-migrant synchronous I/O.
- Empty Ray migration fetches now return explicit empty `MigrationInfo` objects. Unexpected receive/decode failures intentionally propagate and fail the SLURM task; do not restore the historical broad `except: pass`. Legacy `W* Imigrants.json` files remain post-filter compatibility outputs, while research conclusions should use the new pre-filter records.
- `Computation.ready()` now makes actor construction an explicit barrier. `IslandRunner` first waits for island 0 (which prepares shared output metadata), then waits for all Computation actors with the configured timeout before starting the algorithms. The legacy 15-second pause remains, so the safety change does not silently shorten the historical start staging.
- `benchmark_manifest.json` is written before the evolutionary loop; `experiment_manifest.json`, `run_metadata.json`, exact `topology.json`, a post-run topology plot and `iterations_per_second.json` accompany the original raw logs. Do not replace raw migrant logs with only summary statistics.
- **Migration interval currently measures evaluation-counter differences**, not generations: `evaluations - last_migration_evolution >= migration_interval`. The port does not change this or signed delay / immigrant acceptance methods.
- Evidence: `hpc_benchmarks/validation_local.json` and the package `validation_report.json`. Locally, 17 tests and two genuine two-island Ray runs (NK60/maxDistance and F29 200D/best, 128 evaluations each) passed. These ran on Windows/Python 3.12/Ray 2.31. Ares/Python 3.10/SLURM and multiple physical nodes still require target-environment validation. Do not infer a need to upgrade the existing Ares Ray version from the local test version.

## 1) Ray/HPC path (primary, based on current inspection)

### Entrypoint chain
1. `hpc_benchmarks/submit_ares_144.sh` -> `run_ares_144.sh` -> `run_ares.sh`, or the current `pilot_run/` pipeline (Ares CPU)
2. `python hpc_benchmarks/run_benchmark.py ...` (named benchmark, topology preflight and full provenance)
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
The benchmark launcher sets this working directory automatically. The builder now resolves `algorithm/configurations/algorithm_configuration.json` relative to its source through `run_hpc/benchmark_configuration.py`, or reads `ISLANDS_CONFIG`. Other legacy logging paths still expect the outer package working directory.

### Current local diagnostic workflow

From the repository root in an existing project-compatible environment:

```bash
python hpc_benchmarks/run_benchmark.py --problem r01_elliptic --dimension 200 --topology ws3 --dry-run
python hpc_benchmarks/run_benchmark.py --problem b03_nk_k4 --dimension 60 --topology complete --diagnostic --islands 2 --evaluations 128 --ray-address local --local-cpus 6
```

The first checks the 144-island configuration without Ray. The second executes
a small CPU diagnostic outside the study; never run it on an HPC login node.
An Athena checkout does not make this CPU runner execute on GPU.

### Historical local run evidence (May 2026; not current launch commands)

The following setup and seven-island paths document an earlier run. Current
`start.py` rejects that old invocation; use the named diagnostic above.
Dependency notes remain useful when selecting a compatible environment.


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
- `torus` is not a good first legacy local topology because the default remains `12 x (island_count // 12)`; the benchmark launcher can pass an explicitly validated shape.

Validated local output from the command above:
- run directory: `logs/260505/Sphe200/120000 7rr-co5ilu5`
- analysis command:
```bash
cd islandsEA/islands_desync
python analyze_migration_delays.py "logs/260505/Sphe200/120000 7rr-co5ilu5"
```

### Current topology limits (September 16, 2026)
`IslandRunner.py` uses `enumerate(..., start=1)` for islands 1..N-1; the old shifted-index warning is obsolete. Study registry: torus/complete/er4/ws3/ba, requested at 144. Torus defaults to 12x12; complete, selected WS3 and selected BA validate at 144. ER4 remains blocked because its supplied graph has 150 nodes. Fixed loaders require exact node counts and valid adjacency hashes; old ER1/ER2/ER3/WS4 are outside the study registry.

### SLURM script status
- Old `run*-hpc.sh` launchers are retired fail-closed stubs; previously some passed only 8 args.
- Historical `.sh.txt` archives still refer to missing `start_bm.py`; do not use them.
- `run_smoke_ring.sh` is **not present** in this repository snapshot (it may exist only in local/HPC-side working copies).
- Use documented named submitters and pilot_spec.json. Retired scripts are fail-closed stubs, not runnable templates. Supported Ares benchmark/pilot submitters require branch `summer_benchmarks_ares`.

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
- Island count, migrant group and interval come from `RunAlgorithmParams`, supplied by the named launcher or legacy `start.py`; similarly named JSON fields do not override them. Study defaults are 144/5/5. The named launcher separately sets environment overrides for benchmark/dimension and GA settings.

In local RabbitMQ path (`run_algorithm.py`):
- island count/migration fields are tied more directly to JSON and CLI assumptions.

Never assume historical example values are authoritative; inspect live config and call path.

---

## Benchmark Selection and Naming Compatibility

### Where the active problem is selected
- Ray/HPC path: `geneticAlgorithm/run_hpc/create_algorithm_hpc.py` via `benchmark_configuration.create_problem`; `ISLANDS_PROBLEM` / JSON `problem`, default `sphere`. Supports `sphere`, `rastrigin` and all 40 names from `benchmarks_refined --list`.
- Legacy local path: `geneticAlgorithm/run_algorithm.py` (currently `Rastrigin(...)`, alternatives commented)
- Custom problems: `geneticAlgorithm/utils/myDefProblems.py` (includes `Ackley`, `Schwefel`, `Labs` placeholders/variants)

### Historical paper settings versus current study
The paper in the repo root reports experiments with:
- `Rastrigin`
- `200` dimensions
- `population_size = 16`
- `offspring_population_size = 4`
- `migration_interval = 5`
- island counts `50`, `100`, `150`, `200`

These island counts describe the historical paper, not the approved 144 study. The builder delegates to `benchmark_configuration.create_problem`; sphere is the fallback only when JSON/environment do not select a problem. The named launcher requires `--problem` and `--dimension`; the pilot explicitly selects `r01_elliptic`, D=200. Neither Sphere nor the historical Rastrigin describes the entire 40-function study.

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
Implemented through `parse_acceptation_strategy`, `filter_new_individuals` and `add_new_individuals`: current names are `plain`, `better`, `newer`, `older`, `oldest`, `stochastic`, `rejectTooOld`, `window`, with existing `dup_` and `:integer` syntax. The historical SAS-only description is obsolete. The benchmark port preserves these methods.

Migration logic is part of the research apparatus, not plumbing. Any semantic change affects comparability.

### Additional research note on destination-side acceptance
The present research direction makes destination-side acceptance especially important. The paper context indicates:
- delayed migrants can be non-trivially harmful or at least inefficient,
- topology changes delay patterns,
- future work includes dedicated immigration operators that may reject too-delayed migrants or use partial information from them.

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

The paper reports topology-dependent min/max behavior and characteristic delay patterns; use percentiles in addition for stronger comparison.

### B. Delivery / acceptance metrics
- received migrants count
- accepted migrants count
- rejected migrants count
- undelivered migrants count (if observable)
- acceptance rate
- rejection rate
- rejection reasons histogram

These are particularly important for ring-like cases, where islands may stop receiving fresh migrants after neighboring islands finish work.

### C. Optimization-outcome metrics
- final best fitness
- final average fitness
- best-so-far fitness over time / epoch
- time-to-threshold (if threshold defined)
- per-island final ranking

The paper compares average and final results across topology/strategy combinations; outcome metrics are mandatory, not optional.

### D. Cooperation / desynchronization metrics
- island active start/end time
- common cooperation window length
- percent of time each island works alone
- active-neighbor count over time
- migrants received per unit time / per epoch
- incoming-queue backlog (if queue exists and is measurable)

The paper explicitly analyzes how long islands cooperate simultaneously and links topology to communication crowding and isolated work.

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
`start.py` uses the selected study registry (torus, complete, er4, ws3, ba), with exactly 144 islands. Ring is diagnostic-only via the named launcher.

### Implementations
- `RingTopology`: current implementation returns `[self, next]` neighbors (non-standard ring; includes self-loop).
- `TorusTopology`: uses 4-neighbor wrapped grid.
- `IslandRunner` retains `create(12, island_count // 12)` as the compatibility default; at 144 this is 12x12. The pilot explicitly records 12 rows and 12 columns. Generic CLI support for other valid shapes does not approve them for the study.

### Known broken/stale topology files
`ERTopology.py`, `WSTopology.py`, `WS1Topology.py`, `WS2Topology.py` reference undefined `topol` variable (commented dict placeholder).  
These legacy names are excluded from current named/positional study registries. Do not substitute them for selected ER4/WS3.

### Selected fixed graph data
`ER4Topology`, `WS3Topology` and `BATopology` wrap `fixed_graph.py` and committed `data/{er4,ws3,ba}.json`. JSON stores exact adjacency, source filename/hash, canonical adjacency hash, parameters and transformation status. Preserve order, loops and direction. ER1/ER2/ER3/WS4 retain legacy inline dictionaries outside the study.

### Research interpretation of topologies
Paper context suggests:
- `complete` creates the largest communication crowding and delay amplitudes, but can still yield the best optimization results due to more diverse migrant inflow,
- `torus` behaves as an intermediate case,
- `ring` is the most orderly but risks long isolated work and lack of fresh migrants once neighbors finish.

Therefore:
- do not evaluate a delay-reduction change solely by smaller delay values,
- always check whether optimization quality improved, degraded, or merely shifted the trade-off.

---

## Output and Logging Contract (Do Not Break)

Output path builder:
- `geneticAlgorithm/utils/filename.py`
- Format resembles:
  - `<run-output-root>/<date>/<prob4><dimension>/<time>_<unique-id> <island_count><migrant_code><topology_code>-co<migration_interval>ilu<emigrants>`
  - Default Ares root: `$SCRATCH/islandsEA/results/runs`; explicit CLI/ISLANDS_RUN_OUTPUT_ROOT overrides take precedence. The `logs/` examples below are historical.

Examples from actual runs:
- `logs/260407/Sphe30/002459 12rr-co20ilu2`

Where:
- `<prob4>` = first 4 letters of problem name
- migrant code = first letter of selection strategy (`r`, `b`, `m`...)
- topology code = first letter (`r`, `t`, `e`, `w`, `c`, `b`...); use full topology name/hash in metadata to identify the graph
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
- named launcher: `iterations_per_second.json` inside the run directory; legacy `start.py`: timestamped summary under the resolved output root
- named launcher also saves exact `topology.json` with parameters/provenance, `topology.png`, `experiment_manifest.json`, `run_metadata.json` and per-island `metrics/` files

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

Use `active_operators` in param/benchmark provenance and the active builder. The old `operators` text field alone is historical and may be misleading.

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
3. Get head node from the scratch-backed SLURM log:
   - `HEAD=$(grep -m1 "Starting HEAD at" "$SCRATCH/islandsEA/logs/slurm/<log-for-JOBID>.out" | awk '{print $4}')`
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
   - `export RUN_DIR="$SCRATCH/islandsEA/results/runs/<date>/<prob4><dim>/<time> <tag>"`
2. Run plotting snippet (inline Python or helper script) that saves:
   - `$RUN_DIR/fitness_all_islands.png`

### File transfer gotchas
- `scp ... .` copies into the current shell location. If run on Ares, file stays on Ares.
- To download to laptop, run `scp` from laptop terminal.
- For the finalized pilot, run `pilot_run/download_pilot.ps1 -JobId <ARRAY_JOB_ID>`
  on the Windows laptop. It resolves remote `$SCRATCH`, downloads into the
  workspace-level `artifacts/pilot_runs/` directory and verifies archive hashes
  and `pilot_summary.json`. Do not stage large transfers through HOME.

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

- study topologies: torus12x12, complete, selected WS3/BA, plus selected ER4 once its 144-node mismatch is resolved
- ring/small-island diagnostics are separate regression tests, not replacements for the study matrix
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
- Current Ares profile: `hpc_benchmarks/run_ares_144.sh`, submitted via `hpc_benchmarks/submit_ares_144.sh`
- Historical stub: `islands_desync/run144tr-hpc.sh` (retired; do not submit)
- Base configuration: `islands_desync/islands_desync/geneticAlgorithm/algorithm/configurations/algorithm_configuration.json`
- Legacy/local problem selection path: `islands_desync/islands_desync/geneticAlgorithm/run_algorithm.py`
- Custom problems: `islands_desync/islands_desync/geneticAlgorithm/utils/myDefProblems.py`
- Migrant source strategy helpers: `islands_desync/islands_desync/geneticAlgorithm/utils/distance.py`

These paths exist, but not all represent equally healthy/maintained runtime paths.
