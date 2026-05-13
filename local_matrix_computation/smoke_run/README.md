# Local Smoke Run

Mini test lokalnego pipeline'u. Sprawdza cztery sciezki:

```text
continous_fixed_toplogies
continous_random_topologies
descrete_fixed_toplogies
descrete_random_topologies
```

Kazda grupa ma jeden `smoke_batch.json` z 2 bardzo malymi jobami. Wyniki trafiaja do odpowiadajacego katalogu w:

```text
local_matrix_computation/smoke_run/results/<grupa>
```

## Regeneracja smoke configow

```powershell
python local_matrix_computation\smoke_run\generate_smoke_configs.py
```

## Najpierw dry-run

```powershell
python local_matrix_computation\run_batch.py local_matrix_computation\smoke_run\runs\continous_fixed_toplogies\smoke_batch.json --dry-run
```

## Najmniejszy realny test

Odpal tylko pierwszy job:

```powershell
python local_matrix_computation\run_batch.py local_matrix_computation\smoke_run\runs\continous_fixed_toplogies\smoke_batch.json --force --limit 1
```

Po sukcesie powinien pojawic sie `summary.csv` i obrazki w:

```text
local_matrix_computation/smoke_run/results/continous_fixed_toplogies/smoke_continous_fixed_toplogies/s0001_smoke_continuous_sphere_ring_random/
```

## Pomiar czasu

Najbardziej porownywalny pierwszy pomiar to jeden continuous fixed run:

```powershell
Measure-Command { python local_matrix_computation\run_batch.py local_matrix_computation\smoke_run\runs\continous_fixed_toplogies\smoke_batch.json --force --limit 1 }
```

Potem mozna zmierzyc dwa joby z tego samego smoke batcha:

```powershell
Measure-Command { python local_matrix_computation\run_batch.py local_matrix_computation\smoke_run\runs\continous_fixed_toplogies\smoke_batch.json --force }
```

`--force` jest celowe przy pomiarach, bo smoke ma stale `date_tag`/`time_tag` i nadpisuje ten sam katalog testowy.

Po przerwanym runie lokalny wrapper sam probuje wykonac `ray stop --force` przed i po nastepnym jobie. Jesli terminal byl ubity recznie w zlym momencie, mozna dodatkowo zrobic:

```powershell
.\.venv\Scripts\ray.exe stop --force
```

## Pelny smoke

```powershell
python local_matrix_computation\run_batch.py local_matrix_computation\smoke_run\runs\continous_fixed_toplogies\smoke_batch.json --force
python local_matrix_computation\run_batch.py local_matrix_computation\smoke_run\runs\continous_random_topologies\smoke_batch.json --force
python local_matrix_computation\run_batch.py local_matrix_computation\smoke_run\runs\descrete_fixed_toplogies\smoke_batch.json --force
python local_matrix_computation\run_batch.py local_matrix_computation\smoke_run\runs\descrete_random_topologies\smoke_batch.json --force
```

Jesli chcesz uzyc konkretnego interpretera/venva:

```powershell
python local_matrix_computation\run_batch.py local_matrix_computation\smoke_run\runs\continous_fixed_toplogies\smoke_batch.json --python .\.venv\Scripts\python.exe --limit 1
```

## Agregacja smoke wynikow

Po smoke runach mozna sprawdzic tez pipeline porownawczy:

```powershell
python local_matrix_computation\aggregate_results.py `
  --results-root local_matrix_computation\smoke_run\results `
  --runs-root local_matrix_computation\smoke_run\runs `
  --output-dir local_matrix_computation\smoke_run\analysis
```

Wyniki trafiaja do:

```text
local_matrix_computation/smoke_run/analysis/
```

Najwazniejsze pliki:

```text
combined_runs.csv
comparison_groups.csv
strategy_ranking.csv
topology_ranking.csv
```

Smoke aggregation sprawdza, czy eksport i porownawcze CSV-y dzialaja. Nie
traktuj smoke rankingow jako wnioskow naukowych, bo smoke ma zbyt malo
powtorzen.
