# Pilot Ares: torus 10×20, F1 200D, trzy powtórzenia

Ten katalog definiuje **jeden wariant eksperymentu** uruchomiony w trzech
równoległych powtórzeniach jako tablica SLURM. Nie jest to lokalny benchmark.
Autorytatywna konfiguracja znajduje się w `pilot_spec.json`.

## Zamrożona konfiguracja

| Pole | Wartość |
|---|---:|
| benchmark | `r01_elliptic` (pierwszy ciągły z 40) |
| wymiar | 200 |
| wyspy | 200 |
| topologia | torus 10 wierszy × 20 kolumn |
| selekcja migrantów | `best` |
| akceptacja migrantów | `plain` |
| interwał / liczba migrantów | 5 / 5 |
| ewaluacje na wyspę | 8000 |
| populacja / potomkowie | 16 / 4 |
| kroki na wyspę | 1996 |
| powtórzenia | 1, 2, 3 |
| seed bazowy | 20260912 |

`plain` jest celowym baseline'em: przyjmuje wszystkie odebrane osobniki bez
dodatkowego filtra wieku lub jakości. Macierz `5 × 3 × 40 × 3` z zakresu badań
traktuje trzy warianty jako strategie **wyboru** migrantów; dokument nie narzuca
osobnej strategii przyjęcia. F1 w 200D jest utrwalonym rozszerzeniem IslandsEA,
nie oficjalnym wymiarem CEC2014.

Torus 10×20 jest najbliższym kwadratowi rozkładem 200 wierzchołków. Ponieważ
historyczny kod tworzył wyłącznie torus `12 × (N/12)`, ten kształt jest nową,
jawną decyzją metodologiczną. `submit_pilot.sh` wymaga
`CONFIRM_TORUS_200=1`, aby nie uruchomić kosztownego wariantu przed odpowiedzią
prowadzącego. Pełny pilot wymaga dodatkowo ID zaliczonego canary na tej samej
konfiguracji infrastruktury. Brak któregokolwiek dowodu kończy się przed
`sbatch`.

## Co jest wysyłane

Domyślnie `submit_pilot.sh` tworzy:

1. jedną tablicę SLURM `1-3%3`: trzy powtórzenia wykonują się równolegle;
2. jeden mały job końcowy zależny przez `afterany`, który waliduje, analizuje i
   archiwizuje wszystkie trzy wyniki.

Każde powtórzenie rezerwuje 9 węzłów × 48 CPU = 432 CPU, czyli 401 wymaganych
CPU Ray, zapas na procesy Ray i jeden CPU wyłączony z puli Ray dla drivera.
Przy trzech równoległych elementach maksymalna chwilowa alokacja to 27 węzłów i
1296 CPU. Limit 30 minut daje sufit **648 CPUh** dla obliczeń; finalizer dodaje
maksymalnie 1 CPUh. To limit bezpieczeństwa, nie prognoza czasu. Nie ma
automatycznych retry.

## Przed wysłaniem

Na Aresie, z katalogu repozytorium:

```bash
cd ~/islandsEA_student_fork
git pull --ff-only
git status --short

module load python/3.10.4-gcccore-11.3.0
source "$HOME/venvs/islands-ray/bin/activate"

mapfile -t ARGS < <(python pilot_run/pilot_tools.py benchmark-args --repeat 1)
python hpc_benchmarks/run_benchmark.py "${ARGS[@]}" --dry-run
```

Wszystkie trwałe dane generowane przez joby używają wspólnego kontraktu
`hpc_benchmarks/ares_storage.sh`. Na Aresie domyślna struktura to:

```text
$SCRATCH/islandsEA/
├── results/
│   ├── runs/                 # surowe wyniki każdego powtórzenia
│   ├── audit/                # małe manifesty także po błędzie
│   └── pilot_runs/           # finalizacja, archiwa i podsumowanie pilota
├── logs/
│   ├── slurm/                # stdout/stderr jobów
│   └── ray_failures/         # logi Ray zbierane tylko po awarii
├── checkpoints/
└── tmp/
```

Repo i venv pozostają w HOME. Ray oraz cache Matplotlib używają szybkiego,
lokalnego `/tmp` danego węzła, który jest sprzątany po jobie; nie obciąża on
quota HOME. Każdą ścieżkę można nadpisać zmiennymi `ISLANDS_*_ROOT`, a surowe
wyniki i audyt także argumentami `--output-root` i `--audit-root`. Brak
`$SCRATCH` powoduje jawne ostrzeżenie i fallback do `$HOME/islandsEA`.

`git status --short` ma być pusty. Dry-run nie startuje Ray ani obliczeń; powinien
pokazać m.in. 200 wysp, torus 10×20, 401 CPU Ray oraz 402 minimalne CPU SLURM.

Po potwierdzeniu metodologii uruchom najpierw canary: te same 200 wysp i pełne
401 aktorów Ray wraz z torusem, ale tylko 128 ewaluacji na wyspę oraz 10 minut walltime. Jego sufit to
72 CPUh:

```bash
CONFIRM_TORUS_200=1 bash pilot_run/submit_canary.sh
```

Skrypt wypisze `PILOT_CANARY_JOB_ID`. Po zakończeniu nie wystarczy samo spojrzenie
na `squeue`; pełny submit sam sprawdzi `sacct`, kod 0, manifesty, topologię, 200
krzywych i obecność migracji z katalogu canary. Dopiero wtedy:

```bash
CONFIRM_TORUS_200=1 \
PILOT_CANARY_JOB_ID=TU_WSTAW_ID \
bash pilot_run/submit_pilot.sh
```

Domyślnie wszystkie trzy próby biegną równolegle, zgodnie z założeniem pilota.
Jeśli przed właściwym wysłaniem chcesz ograniczyć jednoczesny koszt, jawnie użyj
`PILOT_MAX_PARALLEL=1` lub `2`; nie zmienia to samych konfiguracji powtórzeń.

Skrypt odmawia wysłania z brudnego drzewa Git. Wypisuje ID tablicy, ID finalizera
i katalog artefaktów. Monitorowanie:

```bash
squeue -j ARRAY_JOB_ID,FINALIZER_JOB_ID
sacct -j ARRAY_JOB_ID,FINALIZER_JOB_ID \
  --format=JobID,JobName,State,ExitCode,Elapsed,AllocCPUS,CPUTimeRAW,MaxRSS
```

## Kryterium sukcesu i wyniki

Samo `COMPLETED` albo obecność `BENCHMARK_RUN_OK` nie wystarcza. Finalizer
sprawdza między innymi:

- zgodność manifestu z pełną specyfikacją, czysty commit i sondy wszystkich
  dziewięciu węzłów;
- dokładną listę sąsiadów torusa 10×20;
- 200 kompletnych krzywych po 1996 kroków, skończone fitnessy i wyniki końcowe;
- komplet plików migrantów i rankingów dla każdej wyspy;
- 200 rekordów czasu/iterations-per-second;
- pełny profil `research-v1-full-buffered` dla każdej z 200 wysp: zdarzenia
  migracji, kolejki, fitness, placement aktora i końcowy genotyp;
- punkt początkowy i każdy z 1996 kroków historii fitness oraz diversity;
- identyfikatory źródła/celu migrantów, zgodność liczników i brak odrzucenia
  przez strategię `plain`;
- 200 końcowych wektorów długości 200 wraz ze sprawdzonym SHA-256;
- zgodność metadanych benchmarku, w tym oznaczenie D=200 jako rozszerzenia.

Docelowy katalog to:

```text
$SCRATCH/islandsEA/results/pilot_runs/<ARRAY_JOB_ID>/
```

Najważniejsze pliki:

```text
submission.json
sacct.txt
pilot_summary.json
repeat-1..3/
  attempt.json
  result_pointer.json
  raw_results.tar.gz
  raw_results.tar.gz.sha256
  ray_failure_logs/                 # tylko gdy wrapper zawiedzie
  verified/
    validation.json
    experiment_manifest.json
    run_metadata.json
    benchmark_manifest.json
    param.json
    topology.json
    topology.png
    iterations_per_second.json
    metrics_data_contract.json
    analysis_summary.json
    top_bottom_delay_summary.json
    top_bottom_delay_patterns.png
    delay_heatmap.png
    delay_ecdf.png
    fitness_progress_summary.png
    active_island_count.png
```

W surowym katalogu każdego powtórzenia znajduje się dodatkowo:

```text
metrics/
  data_contract.json
  island_000..199/
    migration_events.jsonl.gz
    queue_fetches.jsonl.gz
    fitness_history.jsonl.gz
    final_solution.json
    runtime.json
    summary.json
```

Zdarzenie migracji ma wspólne `event_id` dla rekordu nadawcy i odbiorcy oraz
etapy `send → enqueue → dequeue → process → filter → replacement`. Rejestrowane
są m.in. kroki i ewaluacje obu stron, fitness migranta, najlepszy fitness
odbiorcy przed decyzją, powód decyzji, czasy Unix, czas w kolejce mierzony
zegarem monotonicznym odbiorcy, głębokość kolejki, przeżycie replacementu i
przeżycie horyzontu 25 kroków. Nierozstrzygnięty horyzont przy końcu runa ma
wartość `null`, a nie fałszywe `false`. Survival dotyczy dokładnego
otagowanego migranta pozostającego w populacji; potomkowie nie dziedziczą tagu,
więc nie jest to miara genealogiczna.

Historia fitness zawiera best/current, best-so-far, średnią, medianę, najgorszy
wynik, odchylenie standardowe (`ddof=0`), diversity i osie step/evaluations/time.
`pilot_summary.json` agreguje trzy powtórzenia (raportuje `ddof=0` i `ddof=1`) i
parsuje z `sacct` rzeczywiste CPUh, `TotalCPU`, efektywność oraz MaxRSS, jeżeli
klaster zwróci te pola. Topologia ma dokładny hash adjacency, liczby krawędzi,
stopnie, pętle, gęstość i testy spójności.

Telemetria jest buforowana w pamięci każdej wyspy i zapisywana w gzip dopiero po
zakończeniu optymalizacji. Dzięki temu nie dokładamy synchronicznego I/O do
każdej migracji i nie zniekształcamy mierzonego delay.

Canary zapisuje osobno
`$SCRATCH/islandsEA/results/pilot_runs/pilot_canaries/<JOB_ID>/result_pointer.json`
i `canary_validation.json` (tworzony przy zgłoszeniu pełnego pilota). Logi z
nieudanego startu Ray trafiają do `$SCRATCH/islandsEA/logs/ray_failures/`.

`pilot_summary.json` ma mieć `"valid": true`, `"valid_repeats": 3`, a log
finalizera linię `PILOT_VALIDATION_OK`. Analiza zachowuje metryki optymalizacji,
opóźnień, dostarczeń, tempa migrantów i użyteczności oraz osobne charakterystyki
opóźnień dla 10 najlepszych i 10 najgorszych wysp. Znak delay pozostaje:
`iteracja źródła przy wysłaniu - krok odbiorcy przy przyjęciu`.

Archiwum nie usuwa surowego katalogu ze scratcha. Na laptopie helper sam odczyta
wartość zdalnego `$SCRATCH`, pobierze wynik do głównego katalogu `artifacts` i
sprawdzi wszystkie archiwa oraz `pilot_summary.json`:

```powershell
cd C:\Users\piotr\UMISI\IslandsEA_summer\main_codebase\islandsEA_student_fork
.\pilot_run\download_pilot.ps1 -JobId ARRAY_JOB_ID
```

Domyślny cel to
`C:\Users\piotr\UMISI\IslandsEA_summer\artifacts\pilot_runs\<ARRAY_JOB_ID>`.
Można podać `-Remote` lub `-Destination`. Dopiero po komunikacie
`PILOT_DOWNLOAD_OK` osobno zdecyduj o czyszczeniu scratcha. Scratch jest
przestrzenią roboczą, a nie trwałym backupem.

Każde powtórzenie ma `run_metadata.json`, przeznaczony do późniejszej agregacji.
Zawiera pełną konfigurację benchmarku, GA, migracji i topologii, repeat i seedy,
`run_id`, stabilny `experiment_key`, commit i hashe kodu, wersje zależności,
żądane zasoby, identyfikatory SLURM oraz wszystkie ścieżki storage. Pełniejszym
dziennikiem wykonania pozostaje `experiment_manifest.json`.

## Ważne ograniczenia

- Limit walltime zatrzyma zawieszony lub zbyt wolny run, ale nie jest
  checkpointem.
- Nieoczekiwany błąd odbioru migrantów przerywa teraz job; pustą kolejkę obsługuje
  jawny pusty pakiet. Historyczne `except: pass` nie ukrywa już utraty danych.
- Stare `Imigrants.json` nadal opisuje dane po filtrze dla kompatybilności.
  Pełny rejestr przed filtrem i liczniki końcowej kolejki są w `metrics/`.
- Snapshoty końcowych kolejek są robione po barierze zakończenia algorytmów, ale
  nie stanowią dodatkowej bariery per wiadomość; dokładną interpretację opisuje
  `data_contract.json`.
- 200D F1 służy jako pierwszy ciągły pilot infrastruktury. Jego czas nie będzie
  reprezentatywny dla najdroższych hybryd i kompozycji.
