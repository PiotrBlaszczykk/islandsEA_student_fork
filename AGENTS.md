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
