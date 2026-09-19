> **Artefakty runa od 2026-09-19:** wspólny format CPU/GPU to
> `run_<job_id>/{logs,metrics,results}`, `identifier.txt`, `metdadata.json`
> oraz `run_<job_id>.tar.gz` + SHA-256 w `$SCRATCH/islandsEA/exports`.
> [Układ, eksport i pobieranie](<../hpc_benchmarks/RUN_ARTIFACTS.md>). Dawne raw/audit i archiwa pilota
> są zachowane dla zgodności; nowy downloader to `hpc_benchmarks/download_run.ps1`.

> Aktualizacja 2026-09-17: badanie używa 144 wysp we wszystkich topologiach.
> ER4 został odblokowany zgodnie z odpowiedzią prowadzącej: igraph G(n,p),
> n=144, p=0.0347, undirected; pętle tylko dla izolowanych węzłów.
> Zamrożony graf ma 365 krawędzi, składową 144 i zero pętli; seed 20260917.
> Szczegóły: [generacja ER4](../hpc_benchmarks/ER4_GENERATION.md).
> Historyczne pomiary i stare załączniki pozostają archiwalne; D=200 jest wymiarem.

# Pilot Ares: torus 12×12, F1 200D, trzy powtórzenia

Ten katalog definiuje **jeden wariant eksperymentu** uruchomiony w trzech
równoległych powtórzeniach jako tablica SLURM. Nie jest to lokalny benchmark.
Autorytatywna konfiguracja znajduje się w `pilot_spec.json`.

## Zamrożona konfiguracja

| Pole | Wartość |
|---|---:|
| benchmark | `r01_elliptic` (pierwszy ciągły z 40) |
| wymiar | 200 |
| wyspy | 144 |
| topologia | torus 12 wierszy × 12 kolumn |
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

144 wyspy zatwierdzono w mailu; torus12×12 zachowuje dotychczasowe 12 kolumn. Bramka CONFIRM_TORUS_200 została usunięta. Nadal wymagane są ID poprawnego canary na tej samej konfiguracji oraz przypięty czysty commit.

## Co jest wysyłane

Domyślnie `submit_pilot.sh` tworzy:

1. jedną tablicę SLURM `1-3%3`: trzy powtórzenia wykonują się równolegle;
2. jeden mały job końcowy zależny przez `afterany`, który waliduje, analizuje i
   archiwizuje wszystkie trzy wyniki.

Każde powtórzenie rezerwuje 7 węzłów × 48 CPU = 336 CPU, czyli 289 wymaganych
CPU Ray, zapas na procesy Ray i jeden CPU wyłączony z puli Ray dla drivera.
Przy trzech równoległych elementach maksymalna chwilowa alokacja to 21 węzłów i
1008 CPU. Limit 30 minut daje sufit **504 CPUh** dla obliczeń; finalizer dodaje
maksymalnie 1 CPUh. To limit bezpieczeństwa, nie prognoza czasu. Nie ma
automatycznych retry.

## Jednokomendowe uruchomienie całego pipeline'u

Po `git pull --ff-only` jeden launcher wykonuje testy, dry-run, sprawdza czysty
commit i storage pod `$SCRATCH`, wysyła canary, a następnie mały job-bramkę.
Bramka działa przez zależność SLURM `afterany`, więc nie wymaga otwartej sesji
SSH. Sprawdza wynik canary i **tylko po pełnej walidacji** automatycznie wysyła
trzy właściwe powtórzenia oraz finalizer:

```bash
bash pilot_run/launch_pilot.sh --confirm-144-and-562-cpuh
```

Argument jest celowo długi: potwierdza koszt pipeline’u ≤561.5 CPUh (zaokrąglony limit 562). Canary oraz właściwe joby są przypięte do commita obecnego przy
uruchomieniu. Zmiana checkoutu lub brudne drzewo przed startem któregokolwiek
etapu bezpiecznie zatrzyma pipeline. Launcher nie wykonuje automatycznych retry.

## Ręczne uruchomienie etapami

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
pokazać m.in. 144 wysp, torus 12×12, 289 CPU Ray oraz 290 minimalne CPU SLURM.

Uruchom najpierw canary: te same 144 wysp i pełne
289 aktorów Ray wraz z torusem, ale tylko 128 ewaluacji na wyspę oraz 10 minut walltime. Jego sufit to
56 CPUh:

```bash
bash pilot_run/submit_canary.sh
```

Skrypt wypisze `PILOT_CANARY_JOB_ID`. Po zakończeniu nie wystarczy samo spojrzenie
na `squeue`; pełny submit sam sprawdzi `sacct`, kod 0, manifesty, topologię, 144
krzywych i obecność migracji z katalogu canary. Dopiero wtedy:

```bash
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
- dokładną listę sąsiadów torusa 12×12;
- 144 kompletnych krzywych po 1996 kroków, skończone fitnessy i wyniki końcowe;
- komplet plików migrantów i rankingów dla każdej wyspy;
- 144 rekordów czasu/iterations-per-second;
- pełny profil `research-v1-full-buffered` dla każdej z 144 wysp: zdarzenia
  migracji, kolejki, fitness, placement aktora i końcowy genotyp;
- punkt początkowy i każdy z 1996 kroków historii fitness oraz diversity;
- identyfikatory źródła/celu migrantów, zgodność liczników i brak odrzucenia
  przez strategię `plain`;
- 144 końcowych wektorów długości 200 wraz ze sprawdzonym SHA-256;
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
