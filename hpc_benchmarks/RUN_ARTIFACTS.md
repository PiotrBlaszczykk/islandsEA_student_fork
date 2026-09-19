# Jeden run, jeden katalog i jedno archiwum

Kontrakt od 19 września 2026 r., wspólny dla Aresa i Atheny. Wzorzec użytkownika:
workspace `artifacts/run_wyniki_przyklad/run_123456` i zebrany run `run_3174577`.

```text
$SCRATCH/islandsEA/exports/
├── run_<SLURM_JOB_ID>/
│   ├── identifier.txt
│   ├── metdadata.json
│   ├── logs/
│   │   ├── <oryginalna-nazwa-joba>.out
│   │   ├── <oryginalna-nazwa-joba>.err
│   │   └── ray_failures/                  # jeżeli wystąpiły
│   ├── metrics/
│   │   ├── data_contract.json
│   │   ├── island_000/
│   │   │   ├── migration_events.jsonl.gz
│   │   │   ├── queue_fetches.jsonl.gz
│   │   │   ├── fitness_history.jsonl.gz
│   │   │   ├── final_solution.json
│   │   │   ├── runtime.json
│   │   │   └── summary.json
│   │   ├── ... island_143/                # wszystkie wyspy; canary wg liczby w metadanych
│   │   └── athena/                        # istniejąca dodatkowa diagnostyka GPU
│   └── results/
│       ├── param.json
│       ├── benchmark_manifest.json
│       ├── experiment_manifest.json
│       ├── run_metadata.json
│       ├── topology.json
│       ├── topology.png
│       ├── iterations_per_second.json
│       ├── ___RESULT.txt, ___WINNER.txt
│       ├── W*..., resultsEveryStepW*, kontrolW*..., wykresy...
│       ├── result_pointer.json
│       ├── validation.json               # gdy walidator joba je utworzył
│       ├── environment-check.json, pip-freeze.txt, nvidia-smi.csv
│       │                                  # jeżeli dany backend je zebrał
│       ├── verified/                      # istniejąca analiza/walidacja pilota CPU
│       └── bundle_manifest.json
├── run_<SLURM_JOB_ID>.tar.gz
└── run_<SLURM_JOB_ID>.tar.gz.sha256
```

Pisownia **`metdadata.json`** pochodzi z przekazanego wzorca i jest zachowana
celowo. Plik jest dokładną kopią `results/run_metadata.json`; nie zmieniamy
schematu ani historycznych ścieżek zapisanych w naukowych metadanych.
`results/bundle_manifest.json` podaje przenośne ścieżki względem katalogu runa,
mapowanie źródeł, rozmiary i SHA-256 wszystkich pozostałych plików. Nie należy
otwierać oryginalnych ścieżek HPC z `result_pointer.json` po pobraniu na laptop.

`identifier.txt` podaje job/run ID, powtórzenie, platformę/backend, benchmark,
wymiar, topologię, migrację, status i commit. `bundle_complete=true` oznacza
komplet wymaganych plików i zakończone obliczenia. **Nie jest oceną wyniku
naukowego**: `validation=passed/failed/not_run/unknown` jest osobną informacją.
Nie oznaczamy niewykonanej walidacji CPU jako zaliczonej.

## Wspólne dane CPU/GPU

Obie platformy zachowują ten sam kontrakt `research-v1-full-buffered`, sześć
plików na wyspę, historię fitness, migracje, kolejki, signed delay, przeżycie
migrantów, wyniki i metadane topologii. Nic nie jest usuwane z surowych wyników,
agregowane zamiast rekordów ani przeliczane podczas eksportu. Zachowane są
ujemne opóźnienia, wartości `null`, kolejność rekordów i oryginalne bajty gzip.

Kontrola kodu potwierdziła identyczne metody zapisu metryk, fitness i survival
oraz wszystkie 21 wspólnych pól `runtime.json`. Athena zachowuje dodatkowe
pola shardów/schedulera i `metrics/athena/` z requestami/batchami GPU. Ares nie
ma fikcyjnych pomiarów GPU. Układ głównych katalogów i wspólne dane badawcze
są takie same; diagnostyka sprzętowa pozostaje odpowiednia dla platformy.

Eksport działa **po obliczeniach i zakończeniu zapisu metryk**. Nie dodaje I/O
do pętli GA, nie zmienia barier, RNG ani zakresu mierzenia opóźnień. Koszt
pakowania należy do czasu joba, ale nie do okna obliczeń algorytmu.

## Automatyczny eksport na SCRATCH

- Ares: `hpc_benchmarks/run_ares.sh` pakuje run po zamknięciu procesów Ray.
  Działa też dla canary i standardowych submitterów. Nowe zwykłe joby zapisują
  pointer w `results/job_evidence/<job_id>/result_pointer.json`.
- Pilot CPU: `run_pilot_array.sh` najpierw zamyka `attempt.json`, potem pakuje
  run. Finalizer odświeża pakiet po zapisaniu walidacji i analizy. Każdy repeat
  dostaje **własny rzeczywisty `SLURM_JOB_ID`**; nie używamy jednego ID całej
  tablicy jako nazwy wszystkich trzech runów.
- Athena: `athena_gpu/run_study_job.sh` pakuje wyniki po walidatorze i cleanup.
  Udany benchmark z nieudaną walidacją zachowuje `validation=failed`.
- Pakiety niekompletnych/nieudanych jobów mają `complete=false` i listę braków.
  Błąd eksportu nie kasuje danych źródłowych. Jeśli obliczenia były udane,
  błąd pakowania powoduje kod joba 74; wcześniejszy kod awarii pozostaje zachowany.

Katalog można nadpisać przez `ISLANDS_EXPORT_ROOT`. Domyślna ścieżka to
`$ISLANDS_STORAGE_ROOT/exports`, zwykle `$SCRATCH/islandsEA/exports`.
Marker w logu: `RUN_BUNDLE_ARCHIVE=.../run_<job_id>.tar.gz`.

Stare wewnętrzne raw/audit paths i archiwa pilota `raw_results.tar.gz` pozostają
dla zgodności istniejącej walidacji. Podstawowym artefaktem pojedynczego runa
do pobrania jest teraz `run_<job_id>.tar.gz`. `download_pilot.ps1` zachowuje
dotychczasową obsługę zbiorczego pilota; do nowego formatu służy `download_run.ps1`.
Cache CUDA/Matplotlib, tmp i wcześniejsze archiwa nie wchodzą do nowej paczki.

Eksport w końcowej fazie wrappera robi migawkę `.out/.err` przed epilogiem
SLURM i przed wypisaniem samego komunikatu o archiwum. Aby mieć również
ostatnie komunikaty SLURM, po zakończeniu joba wykonaj eksport ponownie z
`--replace`. Finalizer pilota wykonuje odświeżenie po zakończeniu zadań tablicy.
Po SIGKILL, OOM lub twardym limicie czasu trap może nie dostać czasu na eksport;
dostępne dane można zebrać ręcznie z `--allow-incomplete`.

## Eksport ręczny i odświeżenie

Z repozytorium na klastrze, w istniejącym venv, po zakończeniu runa:

```bash
# Ares: użyj pointera ze zwykłego joba albo odpowiedniego repeat/canary pilota.
python hpc_benchmarks/run_bundle.py export --platform ares --job-id 123456 \
  --pointer "$SCRATCH/islandsEA/results/job_evidence/123456/result_pointer.json" \
  --log-dir "$SCRATCH/islandsEA/logs/slurm" --replace

# Athena: dla canary zamień athena_study_runs na athena_study_canaries.
python hpc_benchmarks/run_bundle.py export --platform athena --job-id 3174577 \
  --pointer "$SCRATCH/islandsEA/results/athena_study_runs/3174577/result_pointer.json" \
  --log-dir "$SCRATCH/islandsEA/logs/slurm" --replace
```

Można wskazać `--raw /dokladny/katalog/runa` i opcjonalnie `--job-dir` oraz
powtarzane `--log /sciezka/do/logu`. Obsługiwany jest też już uporządkowany
katalog według wzorca użytkownika. Eksporter odrzuca kolizje nazw o różnej
treści, niezgodne job/run ID oraz podmianę pakietu innego runa/platformy.
`--replace` działa wyłącznie na własnym pakiecie z manifestem.
Źródła są kopiowane, nigdy przenoszone ani usuwane.

## Pobranie na Windows

Polecenia wykonywać **na laptopie**, z właściwego repozytorium:

```powershell
.\hpc_benchmarks\download_run.ps1 -Platform athena -JobId 3174577 -Extract
.\hpc_benchmarks\download_run.ps1 -Platform ares -JobId 123456 -Extract
```

Domyślnie zapisuje w workspace `artifacts/run_wyniki/<platforma>/`. Można
podać `-Remote user@host`, `-Destination`, `-RemoteExportRoot` lub `-Python`.
Bez `-Extract` pobierane są tar.gz i checksum, a SHA-256 archiwum jest sprawdzane.
`-Extract` wymaga lokalnego Pythona: przed rozpakowaniem weryfikuje również
każdy plik wewnątrz archiwum. Skrypt nie nadpisuje wcześniejszych pobrań.

Można nadal użyć zwykłego `scp` dla archiwum i `.sha256`, a następnie:

```bash
python hpc_benchmarks/run_bundle.py verify /sciezka/run_123456.tar.gz
```

Analizator opóźnień akceptuje katalog `run_<id>` albo jego `results/` i odczytuje
metryki z sąsiedniego `metrics/`; stare katalogi raw nadal są obsługiwane.
Walidatory klastra i pilotowe pointery nadal odnoszą się do oryginalnego raw.

## Sprawdzenia lokalne

```bash
python -m unittest discover -s hpc_benchmarks -p test_run_bundle.py
python -m unittest discover -s hpc_benchmarks -p test_bundle_integration.py
```

Dowody bieżącej zmiany są w workspace `artifacts/run_layout_20260919/`,
w tym eksport i kontrola rzeczywistego przykładu 3174577. To lokalne sprawdzenia;
nie są nowym uruchomieniem GA na Aresie lub Athenie.
