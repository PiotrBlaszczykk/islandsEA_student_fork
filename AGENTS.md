# AGENTS.md

## Scope
This repository is a research codebase for asynchronous island-model evolutionary computation.  
Treat experiment correctness and reproducibility as the primary goal. Do not optimize for refactor cleanliness at the cost of changing semantics.
This document is based primarily on current repository/code inspection; validate runtime assumptions in the target environment (HPC/local) before high-impact changes.

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

### Working-directory requirement
Run from outer `islands_desync/` directory.  
`create_algorithm_hpc.py` loads config from:
- `./islands_desync/geneticAlgorithm/algorithm/configurations/algorithm_configuration.json`

That relative path assumes CWD is outer `islands_desync/`.

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

---

## Dependencies and Environment

`algorithm/requirements.txt` is not sufficient for successful Ray/HPC startup by itself.

Likely required extras for the current code path (based on imports and current requirements file contents):
- `ray`
- `scikit-learn` (imported by `utils/tsne.py` at module import time, even if TSNE output flags are false)

If environment setup changes, validate imports before submitting jobs.

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

## Student Continuous Benchmark Workflow (Validated on Ares)

Student-owned benchmark tooling lives in:
- `islands_desync/students_tests/continous_benchmarks/`

Important files:
- `benchmark_matrix_smoke.csv` - small smoke matrix.
- `benchmark_matrix_full_continuous.csv` - current stable full matrix.
- `generate_full_matrix.py` - regenerates the stable full matrix.
- `submit_matrix.sh` - submits one SLURM job per CSV row.
- `run_one_benchmark_hpc.sh` - generic one-run SLURM/Ray wrapper.
- `plot_topology.py` and `summarize_experiments.py` - postprocessing/export helpers.

### Current stable research matrix
The current stable continuous matrix is:

```text
3 objective functions x 3 topologies x 4 migrant strategies x 3 island counts x 3 repeats = 324 jobs
```

Values:
- objective functions: `sphere`, `rastrigin`, `ackley`
- topologies: `ring`, `torus`, `complete`
- island counts: `48`, `96`, `144`
- migrant source strategies: `random`, `best`, `worst`, `maxDistance`
- repeats: `r1`, `r2`, `r3`
- fixed GA parameters: `number_of_variables=200`, `number_of_evaluations=8000`, `population_size=16`, `offspring_population_size=4`
- fixed migration parameters: `number_of_migrants=5`, `migration_interval=5`, `migrant_accept_strategy=BEZ`

Current resource mapping:

```text
48 islands  ->  4 nodes,  96 tasks, 01:00:00
96 islands  ->  6 nodes, 144 tasks, 01:30:00
144 islands ->  8 nodes, 192 tasks, 02:00:00
```

Do **not** put `288` islands back into the default matrix. Treat `288` as a separate stress test only.
Probe runs with `288` reached `Ray cluster is ready`, but then Ray workers died with `SYSTEM_ERROR` / `ActorDiedError` / connection EOF, likely due to process/memory pressure at that scale on Ares. At that point the experiment becomes a Ray/SLURM stress test rather than a clean topology/migration experiment.

### Ares submit workflow
From outer `islands_desync/` on Ares:

```bash
git fetch origin
git reset --hard origin/smoke_tests

awk -F, 'NR>1 {count[$7]++} END {for (k in count) print k, count[k]}' \
  students_tests/continous_benchmarks/benchmark_matrix_full_continuous.csv | sort -n

grep ',288,' students_tests/continous_benchmarks/benchmark_matrix_full_continuous.csv

SUBMIT_SLEEP_SECONDS=2 bash students_tests/continous_benchmarks/submit_matrix.sh \
  students_tests/continous_benchmarks/benchmark_matrix_full_continuous.csv
```

Expected matrix count:

```text
48 108
96 108
144 108
```

`grep ',288,' ...` should print nothing.

### Sanity checks during a full run
Use the submitted job range for the current batch (for example `20078714-20079050`).

Queue state:

```bash
squeue -u $USER -h -o "%T" | sort | uniq -c
```

Accounting state:

```bash
sacct -j <FIRST_JOB_ID>-<LAST_JOB_ID> --format=State -n -X | sort | uniq -c
```

Failures:

```bash
sacct -j <FIRST_JOB_ID>-<LAST_JOB_ID> --format=JobID,JobName,State,ExitCode,Elapsed -X \
  | grep -E "FAILED|CANCELLED|TIMEOUT|OUT_OF_MEMORY|NODE_FAIL" || true
```

Export progress:

```bash
find students_tests/continous_benchmarks/exports/<YYMMDD> -path "*_full_*" -name summary.csv | wc -l
```

Expected final count for the stable full matrix: `324`.

`COMPLETING` / truncated `COMPLETI` in `squeue` is usually normal SLURM cleanup. `PENDING (Priority)` and `PENDING (Resources)` are normal queue states, not failures.

### Known Ares failure modes and fixes

1. `sbatch: error: Invalid --time specification`
   - Usually caused by Windows CRLF in CSV, so `time_limit` becomes `01:00:00\r`.
   - Fix on Ares if needed:
     ```bash
     sed -i 's/\r$//' students_tests/continous_benchmarks/benchmark_matrix_full_continuous.csv
     ```
   - The benchmark directory has `.gitattributes` and the generator uses `lineterminator="\n"` to prevent this.

2. Ray worker startup timeout before the algorithm starts
   - Symptom: `The current node timed out during startup`.
   - `run_one_benchmark_hpc.sh` now:
     - derives Ray ports from `SLURM_JOB_ID`,
     - sets `RAY_raylet_start_wait_time_s=300`,
     - exports `RAY_ADDRESS=$ip_head`,
     - waits for the head port,
     - waits until Ray reports all SLURM nodes alive before calling `start.py`.
   - Do not remove those waits unless replacing them with an equivalent readiness check.

3. `FileNotFoundError` for `logs/.../kontrolW<id>Start.ctrl.txt`
   - Cause: many islands start concurrently; nonzero islands can try to write before island `0` creates the log directory.
   - Required safeguards:
     - `geneticAlgorithm/utils/controller.py` must create `katalog` with `os.makedirs(katalog, exist_ok=True)` before opening control files.
     - `genetic_island_algorithm.py` should use `os.makedirs(self.path, exist_ok=True)` for island `0`.

4. Ray over-reservation / worker death from helper actors
   - `Computation` is the CPU-heavy actor and should keep `@ray.remote(num_cpus=1)`.
   - `Island` and `SignalActor` are helper/state actors and should stay `@ray.remote(num_cpus=0)`.
   - Setting helper actors back to `num_cpus=1` roughly doubles Ray's logical CPU demand (for 288 islands it creates 288 `Computation` actors, 288 `Island` actors, and 1 `SignalActor`).

5. Avoid submitting the full matrix before a smoke/probe has worked after code changes.
   - Smoke matrix should produce `summary.csv`, `summary.json`, `fitness_all_islands.png`, `topology_with_fitness.png`, and `topology_metrics.json`.
   - For orchestration changes, run at least one representative `144`-island probe before the full matrix.

---

## Before Making Changes
1. Identify which execution path is affected (Ray/HPC vs legacy RabbitMQ/local).
2. Trace real call graph from entrypoint before editing.
3. Check whether change touches high-risk experiment-critical areas.
4. Inspect config consumption in code (do not trust historical docs blindly).
5. Verify topology/problem/logging implications.
6. Note any mismatch between docs/scripts and live code.

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
7. State clearly what was validated and what was not (especially HPC paths).

---

## Never Do This
- Do not perform drive-by refactors in core experimental code.
- Do not remove "noisy" logs/output files without explicit request.
- Do not change benchmark naming conventions casually.
- Do not silently alter parameter meaning or units.
- Do not modify migration/topology semantics without noting experiment comparability impact.
- Do not claim success if only static edits were done and no minimal run/import validation was performed.

---

## Safe-ish Extension Points

Lower-risk additions:
- Add new benchmark problems in `geneticAlgorithm/utils/` (ensure unique first 4 letters in `get_name()`).
- Add analysis/visualization scripts that consume existing logs.
- Add convenience HPC wrappers/scripts (without changing core algorithm semantics).

Higher-risk additions:
- New migration strategies (source or destination acceptance) in core loop.
- Topology behavior changes.
- Output naming/log schema changes.
- Changes to orchestration barriers/signaling (`SignalActor`, migration pipeline).

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
