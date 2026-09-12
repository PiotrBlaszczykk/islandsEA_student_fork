# islandsEA

Research codebase for asynchronous island-model evolutionary computation, focused on migration-delay behavior and topology effects.

## Named benchmarks on Ares

The active Ray builder supports the validated **30 continuous + 10 binary** benchmark suite, including the separately identified IslandsEA 200D extension. See [the HPC guide](hpc_benchmarks/README.md) for SLURM validation, small pilots, resource sizing and full experiment commands. [Local validation evidence](hpc_benchmarks/validation_local.json) includes two completed Ray runs; Ares/SLURM validation remains to be performed on the cluster.

## Local Setup

The current actively maintained path is the Ray-based path in `islands_desync/islands_desync/start.py`.

Recommended local environment:
- `uv`
- `Python 3.10`
- `ray==2.9.3`
- `scikit-learn==1.1.3`
- `setuptools<81`

Example setup:

```bash
cd islandsEA/islands_desync
uv venv -c --python 3.10
uv pip install -r islands_desync/islands_desync/geneticAlgorithm/algorithm/requirements.txt ray==2.9.3 scikit-learn==1.1.3 'setuptools<81'
```

Notes:
- The repository pins an older numerical stack. Newer Python versions such as `3.14` do not work with the pinned `numpy==1.21.4`.
- `ray 2.9.x` still expects `pkg_resources`, hence the `setuptools<81` pin.

## Run Locally

Run from the outer `islands_desync/` directory, not from the repository root.

Example validated local run:

```bash
source .venv/bin/activate
cd islandsEA/islands_desync
dda=$(date +%y%m%d)
tta=$(date +%H%M%S)
PYTHONPATH="$PWD" python -u islands_desync/start.py 7 /tmp/islands-ray 5 5 "$dda" "$tta" ring random plain
```

Argument order for `start.py`:
1. `island_count`
2. Ray temp directory
3. `number_of_emigrants`
4. `migration_interval`
5. date tag
6. time tag
7. topology
8. migrant selection strategy
9. migrant acceptance strategy

## Generate Delay Plots

After a run finishes, the output directory will be under `islands_desync/logs/...`.

Example for the validated run above:

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
