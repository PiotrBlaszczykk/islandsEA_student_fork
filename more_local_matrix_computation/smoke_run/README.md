# More Local Smoke Run

Tiny smoke suite for `more_local_matrix_computation`.

It contains 3 jobs:

```text
c01_elliptic       + ring     + 12 islands + 10 variables
c30_composition8   + torus    + 12 islands + 10 variables
d02_trap5          + complete + 12 islands + 20 bits
```

All jobs use:

```text
evaluations: 96
population_size: 16
offspring_population_size: 4
migrant_strategy: random
accept_strategy: plain
migrants: 2
migration_interval: 12
repeat: 1
```

Generate the smoke config:

```powershell
python more_local_matrix_computation\smoke_run\generate_smoke_configs.py
```

Dry-run the whole smoke batch:

```powershell
python more_local_matrix_computation\smoke_run\run_smoke.py --dry-run
```

Run the whole smoke batch:

```powershell
python more_local_matrix_computation\smoke_run\run_smoke.py --force
```

Run only the first smoke job:

```powershell
python more_local_matrix_computation\smoke_run\run_smoke.py --force --limit 1
```

If your shell `python` is not the project venv, pass it explicitly:

```powershell
python more_local_matrix_computation\smoke_run\run_smoke.py `
  --job-python .\.venv\Scripts\python.exe `
  --force
```

Expected exports go under:

```text
more_local_matrix_computation\smoke_run\results\mixed_fixed_toplogies\
```
