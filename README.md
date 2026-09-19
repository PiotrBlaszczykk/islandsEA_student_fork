> **Artefakty runa od 2026-09-19:** wspólny format CPU/GPU to
> `run_<job_id>/{logs,metrics,results}`, `identifier.txt`, `metadata.json`
> oraz `run_<job_id>.tar.gz` + SHA-256 w `$SCRATCH/islandsEA/exports`.
> [Układ, eksport i pobieranie](<hpc_benchmarks/RUN_ARTIFACTS.md>). Dawne raw/audit i archiwa pilota
> są zachowane dla zgodności; nowy downloader to `hpc_benchmarks/download_run.ps1`.

# islandsEA

Research codebase for asynchronous island-model evolutionary computation, focused on migration-delay behavior and topology effects.

## Current study: 144 islands

Read [STUDY_144.md](STUDY_144.md) for the approved 144-island configuration,
selected torus 12x12/complete/WS3/BA graphs and the authorized frozen ER4
(igraph G(144, 0.0347), undirected, seed 20260917; 365 edges, connected, no loops). Ares uses the CPU profile
`submit_ares_144.sh`; the separate Athena checkout uses the same graph in its
sharded GPU runner. Removing the ER4 blocker does not lift the GPU campaign
hold described in Athena's `athena-info/ATHENA_HOW_TO_RUN.md`. The benchmark
definitions and metric schema were not changed by this topology update.

## Named benchmarks on Ares

The active Ray builder supports the validated **30 continuous + 10 binary** benchmark suite, including the separately identified IslandsEA 200D extension. See [the HPC guide](hpc_benchmarks/README.md) for SLURM validation, small pilots, resource sizing and full experiment commands. [Local validation evidence](hpc_benchmarks/validation_local.json) includes two completed Ray runs; Ares/SLURM validation remains to be performed on the cluster.

## Local Setup

The current actively maintained path is the Ray-based path in `islands_desync/islands_desync/start.py`.

Recommended local environment:
- `uv`
- `Python 3.10`
- `ray==2.9.3`
- `click==8.2.1` (CLI Ray 2.9.3 nie działa z Click 8.3)
- `scikit-learn==1.1.3`
- `setuptools<81`

Example setup:

```bash
cd islandsEA/islands_desync
uv venv -c --python 3.10
uv pip install -r islands_desync/islands_desync/geneticAlgorithm/algorithm/requirements.txt ray==2.9.3 click==8.2.1 scikit-learn==1.1.3 'setuptools<81'
```

Notes:
- The repository pins an older numerical stack. Newer Python versions such as `3.14` do not work with the pinned `numpy==1.21.4`.
- `ray 2.9.x` still expects `pkg_resources`, hence the `setuptools<81` pin.

## Run Locally

Use the repository root and an environment containing the project dependencies:

```bash
python hpc_benchmarks/run_benchmark.py --problem r01_elliptic --dimension 200 --topology ws3 --dry-run
python hpc_benchmarks/run_benchmark.py --problem b03_nk_k4 --dimension 60 --topology complete --diagnostic --islands 2 --evaluations 128 --ray-address local --local-cpus 6
```

The first command checks the 144-island study configuration without Ray. The
second is a two-island diagnostic outside the study. Production runs require
144 islands. Use the named launcher for complete topology/benchmark provenance.

## Generate Delay Plots

After a run finishes, the output directory will be under `islands_desync/logs/...`.

Historical example from an earlier local run (paths are archival):

```bash
cd islandsEA/islands_desync
python analyze_migration_delays.py "logs/260505/Sphe200/120000 7rr-co5ilu5"
```

This writes plots and summaries into:

```text
logs/260505/Sphe200/120000 7rr-co5ilu5/analysis_migration
```

Typical outputs:
- `delay_heatmap.png`
- `delay_timeseries.png`
- `fitness_progress_summary.png`
- `cooperation_timeline.png`
- `summary.json`
- `summary.txt`
