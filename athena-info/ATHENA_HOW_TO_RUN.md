# Athena GPU: sprawdzony runbook uruchomieniowy i zapis walidacji

Ostatnia aktualizacja: **2026-09-17** (ER4 i lokalna poprawka runnera;
pomiary GPU poniżej pochodzą z 16 września).

Ten dokument utrwala działającą procedurę dla Atheny, wyniki wykonanych
walidacji oraz znane ograniczenia. Dotyczy wyłącznie brancha
`summer_benchmarks_athena` i kodu z `athena_gpu/`. Nie jest instrukcją dla
Aresa i nie wolno przenosić tutaj profilu CPU Aresa.

Najważniejszy stan na 2026-09-16:

- backend wszystkich 40 benchmarków przeszedł pełną walidację NumPy/CuPy na
  A100;
- canary shardowanego runnera GA przeszedł na A100;
- jeden normalny run F1/D=200/144 wyspy przeszedł technicznie i zachował
  komplet wymaganych danych;
- **kampania jest obecnie wstrzymana do nowego canary i jednego full**:
  normalny run ujawnił silną zależność
  wyniku od pozycji wyspy wewnątrz sharda, słabe łączenie requestów w batche
  oraz jedną niespójność metadanych. Przyczyny poprawiono lokalnie, lecz nie
  zweryfikowano jeszcze nowego commita na A100. Historyczny job jest poprawnym
  dowodem integracji,
  ale nie powinien być jeszcze używany jako wynik naukowy ani szablon do
  zgłoszenia pozostałych runów;
- nie ma automatycznego retry, resubmitu ani przejścia canary -> full;
- commit, push i pull wykonuje użytkownik. Żaden agent ani skrypt nie powinien
  samodzielnie zgłaszać jobów.

Źródła nadrzędne dla parametrów eksperymentu:

- [`../AGENTS.md`](../AGENTS.md);
- [`../STUDY_144.md`](../STUDY_144.md);
- workspace `../../../zakres_badan.md` na laptopie.

## 1. Niezmienny kontrakt badania

Normalny run badawczy ma:

| Parametr | Wartość |
|---|---:|
| Liczba logicznych wysp | 144 |
| Ewaluacje na wyspę | 8000 |
| Łączna liczba ewaluacji | 1 152 000 |
| Populacja | 16 |
| Offspring | 4 |
| Migranci | 5 |
| Interwał migracji | 5 według istniejącego licznika ewaluacji |
| Strategie wyboru | `best`, `random`, `maxDistance` |
| Podstawowa akceptacja | `plain` |
| Powtórzenia | 3 |
| Benchmarki | 30 ciągłych CEC2014 + 10 binarnych |

Liczba 144 nie zmienia wymiaru problemu. Przykładowy pilot używa
`r01_elliptic`, D=200. Jest to jawnie opisana projektowa instancja IslandsEA,
a nie oficjalna instancja CEC2014 D=200.

Aktualna macierz obejmuje torus 12x12, complete, WS3, dostarczony BA oraz ER4.
**ER4 jest odblokowany** po odpowiedzi prowadzącej: nowy, stały graf igraph
G(n=144, p=0.0347), nieskierowany, seed 20260917. Pierwsze losowanie ma
365 krawędzi, jedną składową 144 i zero pętli. Generator dopuszcza najwyżej
3 węzły poza największą składową i dodaje pętle tylko izolowanym węzłom.
Dokładnie ten sam JSON obowiązuje na Aresie i Athenie; WS3/BA pozostają bez
zmian. [Odtwarzanie i proweniencja ER4](../hpc_benchmarks/ER4_GENERATION.md).
Ta zmiana grafu nie usuwa opisanych wyżej powodów wstrzymania kampanii GPU.

## 2. Sprawdzona architektura Atheny

Runner `athena_gpu/run_study.py` mapuje 144 logiczne wyspy na:

- 12 aktorów `IslandShard`, po 12 logicznych wysp;
- jeden wspólny `EvaluationBatcher`;
- jeden wspólny `MigrationRouter`;
- jeden evaluator CuPy z `num_gpus=1`;
- łącznie 15 CPU widocznych dla Ray oraz jeden CPU dla drivera;
- jedną kartę NVIDIA A100-SXM4-40GB.

Każda logiczna wyspa zachowuje własny stan RNG Pythona i NumPy. Ewaluacja
funkcji celu jest wykonywana na GPU; logika GA, migracje i telemetryka pozostają
na CPU. Nie wprowadzono globalnej bariery generacji. Zachowano dotychczasową
semantykę signed delay, częściowego opróżniania kolejek i profilu
`research-v1-full-buffered`.

Od lokalnej poprawki z 17 września fizyczne shardy nie odpowiadają kolejnym
wierszom torusa. ID wysp są porządkowane stabilnym SHA-256, z seedem równym
seedowi powtórzenia; ten sam repeat ma identyczne mapowanie we wszystkich
porównywanych topologiach, benchmarkach i strategiach. Scheduler obraca punkt
startu każdej rundy obsługi i ogranicza sztuczne wyprzedzenie wewnątrz jednego
sharda do dwóch ukończonych kroków. Nie synchronizuje shardów i nie dodaje
globalnej bariery generacji.

Batch steady ma teraz cel 144 wiersze (36 requestów po 4 wiersze) i limit
oczekiwania 50 ms. Te wartości korzystają ze zwalidowanego rozmiaru A100 i
zastępują nieosiągany w praktyce cel 576/timeout 2 ms. Maksymalnie niezależnie
dostępne pozostaje 576 wierszy; nie jest to bariera.

Profil SLURM:

```text
account:       plgintobl-gpu-a100
partition:     plgrid-gpu-a100
nodes/tasks:   1 / 1
GPU:           1 x A100
CPU:           16
RAM:           128000M
canary limit:  00:15:00, maks. 0.25 GPUh
full limit:    02:00:00, maks. 2 GPUh
retry:         wyłączony
```

Sprawdzony kontrakt środowiska:

- Python 3.10.4;
- Ray 2.9.3;
- NumPy 1.21.4;
- SciPy 1.7.3;
- jMetalPy 1.5.5;
- scikit-learn 1.1.3;
- CuPy `cupy-cuda117==10.6.0`;
- fastrlock 0.8.3;
- CUDA runtime 11.7 (`11070`);
- setuptools 58.1.0.

Pełną listę 28 przypiętych dystrybucji sprawdza
`athena_gpu/environment_contract.py`. Job zapisuje wynik do
`environment-check.json`, wykonuje `pip check`, zapisuje `pip-freeze.txt`
i identyfikację GPU w `nvidia-smi.csv` przed uruchomieniem GA.

Lokalny venv `athena_codebase/.venv` nie jest środowiskiem równoważnym
Athenie: sprawdzony stan to Python 3.12.10 i tylko `pip`. Służy co najwyżej do
lokalnych testów, a nie do certyfikacji Ray 2.9.3/CuPy/A100.

## 3. Model pracy: laptop -> Git -> Athena

Kod jest przygotowywany lokalnie w:

```text
C:\Users\piotr\UMISI\IslandsEA_summer\athena_codebase\islandsEA_student_fork
```

Użytkownik wykonuje lokalnie commit i push na branch
`summer_benchmarks_athena`. Następnie łączy się z Atheną:

```bash
ssh plgblaszczykk@athena.cyfronet.pl
```

Na login node:

```bash
cd "$HOME/islandsEA_student_fork"
git switch summer_benchmarks_athena
git pull --ff-only origin summer_benchmarks_athena
git status --short --branch
git rev-parse HEAD
```

Przed submittem muszą być spełnione wszystkie warunki:

```bash
test -n "$SCRATCH"
test -x "$HOME/venvs/islands-ray/bin/python"
test "$(git branch --show-current)" = summer_benchmarks_athena
test -z "$(git status --porcelain --untracked-files=all)"
test "$(git rev-parse HEAD)" = "$(git rev-parse '@{upstream}')"
```

Submitter sam powtarza te kontrole i przypina job do bieżącego commita. Jeśli
checkout zmieni się lub zabrudzi po zgłoszeniu, job kończy się fail-closed.

Ważne: przed ręcznym uruchamianiem Pythona z venv na login node należy
załadować moduł Pythona:

```bash
module load Python/3.10.4
"$HOME/venvs/islands-ray/bin/python" --version
```

Bez modułu może wystąpić:

```text
error while loading shared libraries: libpython3.10.so.1.0: cannot open shared object file
```

Sam job ładuje `Python/3.10.4` i `CUDA/11.7.0`, więc nie trzeba wykonywać tego
ręcznie przed `sbatch`.

## 4. Walidacja wszystkich 40 benchmarków na A100

Ta walidacja sprawdza backend NumPy/CuPy bez uruchamiania wysp i GA. Nie
powinna być ponawiana rutynowo, jeśli implementacja backendu i dane się nie
zmieniły.

Ręczne zgłoszenie, tylko po jawnej decyzji użytkownika:

```bash
cd "$HOME/islandsEA_student_fork"
bash athena_gpu/submit_validation.sh
```

Wyniki:

```text
$SCRATCH/islandsEA/results/athena_benchmark_validation/<JOB_ID>/validation.json
$SCRATCH/islandsEA/results/athena_benchmark_validation/<JOB_ID>/pip-freeze.txt
$SCRATCH/islandsEA/results/athena_benchmark_validation/<JOB_ID>/nvidia-smi.csv
$SCRATCH/islandsEA/logs/slurm/athena-gpu-readiness-<JOB_ID>.out
$SCRATCH/islandsEA/logs/slurm/athena-gpu-readiness-<JOB_ID>.err
```

Sukces wymaga jednocześnie `COMPLETED 0:0`, JSON ze statusem `passed` oraz:

```text
ATHENA_40_CPU_GPU_MATCH=1
ATHENA_40_GPU_VALIDATION_OK=1
ATHENA_40_GPU_VALIDATION_JOB_OK=1
```

### Zapisany wynik: job 3168014

| Pole | Wynik |
|---|---|
| Job | `3168014` |
| Commit | `d9795315f28d06945ab9af46e9cc54e9c8bb8a39` |
| Węzeł | `t0029` |
| SLURM | `COMPLETED`, `0:0` |
| Czas | 47 s |
| Benchmarki | 40 |
| Instancje | 170 |
| Sprawdzone wiersze | 22 016 |
| Globalny RNG | niezmieniony |

Wszystkie markery zostały zapisane. Implementacja i dane backendu użyte przez
późniejszy pełny run nie zostały względem tej walidacji zmienione.

## 5. Canary shardowanego runnera GA

Canary jest obowiązkowy po każdej zmianie runnera, batchera, routera,
telemetrii, środowiska albo konfiguracji joba. Używa 12 wysp, czterech shardów,
128 ewaluacji na wyspę i torusa 3x4.

Zgłoszenie:

```bash
cd "$HOME/islandsEA_student_fork"
bash athena_gpu/submit_study.sh --canary
```

Submitter wypisze między innymi:

```text
ATHENA_STUDY_JOB_ID=<JOB_ID>
ATHENA_STUDY_MODE=canary
ATHENA_STUDY_RESULT=<...>/athena_study_canaries/<JOB_ID>
ATHENA_STUDY_VALIDATION=<...>/validation.json
ATHENA_STUDY_STDOUT=<...>.out
ATHENA_STUDY_STDERR=<...>.err
MAX_GPU_HOURS=0.25
```

Monitorowanie:

```bash
JOB=<JOB_ID>
squeue -j "$JOB" -o "%.18i|%.24j|%.10T|%.10M|%.10l|%R"
sacct -j "$JOB" -P \
  --format=JobIDRaw,JobName,State,ExitCode,Elapsed,ElapsedRaw,AllocCPUS,AllocTRES,TotalCPU,MaxRSS,NodeList
```

Po zakończeniu `squeue` może wypisać `Invalid job id specified`; oznacza to
zwykle tylko, że job zniknął z aktywnej kolejki. Stan rozstrzyga `sacct` oraz
artefakty.

Kontrola wyniku:

```bash
JOB=<JOB_ID>
ROOT="$SCRATCH/islandsEA"
JSON="$ROOT/results/athena_study_canaries/$JOB/validation.json"
OUT="$ROOT/logs/slurm/athena-study-canary-$JOB.out"
ERR="$ROOT/logs/slurm/athena-study-canary-$JOB.err"

sacct -j "$JOB" -P \
  --format=JobIDRaw,JobName,State,ExitCode,Elapsed,AllocCPUS,AllocTRES,TotalCPU,MaxRSS,NodeList
ls -lh "$JSON" "$OUT" "$ERR"
grep -E '^(ATHENA_STUDY_|ATHENA_STUDY_RUN_OK)' "$OUT"
tail -n 120 "$ERR"
```

Sukces wymaga:

```text
ATHENA_STUDY_RUN_OK=<raw-run-directory>
ATHENA_STUDY_CANARY_OK=1
ATHENA_STUDY_JOB_OK=1
```

oraz `status=passed`, `valid=true`, `mode=canary` w `validation.json`.

### Zapisany wynik: job 3174524

| Pole | Wynik |
|---|---|
| Job | `3174524` |
| Commit | `11633ca1c6b246527543f53461f319e712cd32be` |
| Węzeł | `t0015` |
| SLURM | `COMPLETED`, `0:0` |
| Czas | 20 s |
| Zasoby | 16 CPU, 1 GPU, 125 GiB |
| Raw run | `results/runs/260916/r01_200/205904_53efb97551 12bt-co5ilu5` |

Canary wypisał wszystkie trzy wymagane markery i utworzył poprawny
`validation.json`. Nie zgłosił automatycznie joba full.

## 6. Jeden normalny run z macierzy

Full wolno zgłosić wyłącznie ręcznie po zaliczonym canary z dokładnie tego
samego commita. Bramka jest sprawdzana na podstawie `validation.json` canary.

```bash
cd "$HOME/islandsEA_student_fork"
export ATHENA_STUDY_CANARY_JOB_ID=<PASSED_CANARY_JOB_ID>
bash athena_gpu/submit_study.sh \
  --full \
  --confirm-one-of-1800-max-2-gpuh
```

Aktualny full profil jest celowo nierozszerzalny z CLI i uruchamia dokładnie:

```text
r01_elliptic, D=200
144 wyspy, 12 shardów
8000 ewaluacji na wyspę
populacja 16, offspring 4
5 migrantów, interwał 5
torus 12x12
best / plain
repeat 1
seed bazowy 20260912
```

Nie jest to launcher całej macierzy 1800. Każdy kolejny wariant wymaga osobnej,
kontrolowanej decyzji i po usunięciu opisanych niżej problemów.

Kontrola zakończonego full:

```bash
JOB=<JOB_ID>
ROOT="$SCRATCH/islandsEA"
JSON="$ROOT/results/athena_study_runs/$JOB/validation.json"
OUT="$ROOT/logs/slurm/athena-study-full-$JOB.out"
ERR="$ROOT/logs/slurm/athena-study-full-$JOB.err"

sacct -j "$JOB" -P \
  --format=JobIDRaw,JobName,State,ExitCode,Elapsed,ElapsedRaw,AllocCPUS,AllocTRES,TotalCPU,MaxRSS,NodeList
ls -lh "$JSON" "$OUT" "$ERR"
grep -E '^(ATHENA_STUDY_|ATHENA_STUDY_RUN_OK)' "$OUT"
tail -n 120 "$ERR"
```

Sukces techniczny wymaga:

```text
ATHENA_STUDY_RUN_OK=<raw-run-directory>
ATHENA_STUDY_FULL_RUN_OK=1
ATHENA_STUDY_JOB_OK=1
```

oraz `status=passed`, `valid=true`, `mode=full`, brak błędów i właściwy commit
w `validation.json`. Sam stan `COMPLETED` nie wystarcza.

Czytelne podsumowanie JSON dla canary albo full:

```bash
module load Python/3.10.4

"$HOME/venvs/islands-ray/bin/python" - "$JSON" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as source:
    data = json.load(source)

details = data.get("details") or {}
gpu = details.get("athena_metrics") or {}
backend = gpu.get("backend") or {}
router = gpu.get("router") or {}
migration = details.get("migration_integrity") or {}
delivery = details.get("delivery") or {}
environment = details.get("environment") or {}

print("VALIDATION")
print(" status:", data.get("status"))
print(" valid:", data.get("valid"))
print(" mode:", data.get("mode"))
print(" commit:", data.get("git_commit"))
print(" errors:", data.get("errors"))

print("GPU")
print(" requests:", gpu.get("request_count"))
print(" batches:", gpu.get("batch_count"))
print(" rows:", gpu.get("row_count"))
print(" device:", backend.get("device_name"))
print(" backend_calls:", backend.get("calls"))
print(" backend_rows:", backend.get("rows"))
print(" cupy:", backend.get("cupy"))
print(" cuda_runtime:", backend.get("cuda_runtime"))

print("MIGRATION")
print(" sent:", migration.get("sent_records"))
print(" process_records:", migration.get("process_records"))
print(" missing_process:", migration.get("sent_without_process_record_count"))
print(" duplicate_sent:", migration.get("duplicate_sent_event_ids"))
print(" router_received:", router.get("received_total"))
print(" router_queued_at_end:", router.get("queued_at_end"))
print(" unprocessed_records:", delivery.get("unprocessed_records"))

print("ENVIRONMENT")
print(" python:", (environment.get("python") or {}).get("installed"))
print(" environment_status:", environment.get("status"))
PY
```

### Zapisany wynik: job 3174577

| Pole | Wynik |
|---|---|
| Job | `3174577` |
| Commit | `11633ca1c6b246527543f53461f319e712cd32be` |
| Węzeł | `t0002` |
| SLURM | `COMPLETED`, `0:0` |
| Czas | 00:14:11 (851 s) |
| TotalCPU | 01:28:37 |
| MaxRSS | 13 086 776 KiB, około 12.5 GiB |
| GPU | NVIDIA A100-SXM4-40GB |
| Raw run | `results/runs/260916/r01_200/211406_c860e3a1ec 144bt-co5ilu5` |

Walidacja potwierdziła:

```text
status=passed
valid=true
errors=[]
request_count=287568
batch_count=143197
row_count=1152000
backend_calls=143197
backend_rows=1152000
CuPy=10.6.0
CUDA runtime=11070
```

Run zachował wyniki wszystkich 144 wysp i pełną telemetrykę. Jest dowodem, że
cały pipeline działa technicznie, ale ze względu na artefakt shardowania nie
jest jeszcze bezpiecznym wynikiem naukowym.

## 7. Układ wyników i obowiązkowe dane

Całość trafia pod scratch:

```text
$SCRATCH/islandsEA/
  results/
    athena_benchmark_validation/<JOB_ID>/
    athena_study_canaries/<JOB_ID>/
    athena_study_runs/<JOB_ID>/
    runs/<date>/<benchmark>/<raw-run>/
    audit/<run_id>/
  logs/slurm/
  checkpoints/
  tmp/
```

Katalog raw runu musi zawierać co najmniej:

```text
param.json
benchmark_manifest.json
experiment_manifest.json
run_metadata.json
iterations_per_second.json
topology.json
topology.png
metrics/data_contract.json
```

Dla każdej wyspy `metrics/island_NNN/`:

```text
migration_events.jsonl.gz
queue_fetches.jsonl.gz
fitness_history.jsonl.gz
final_solution.json
runtime.json
summary.json
```

Telemetryka GPU w `metrics/athena/`:

```text
athena_evaluation_contract.json
backend.json
evaluation_requests.jsonl.gz
gpu_batches.jsonl.gz
migration_router.json
shards.json
summary.json
```

Zachowywane są również legacy outputs dla każdej wyspy, m.in.
`resultsEveryStepW*.json`, `W* Imigrants.json`, `W* czas.json`, rankingi,
diversity oraz pliki kontrolne. W runie `3174577` każdy wymagany typ wystąpił
dokładnie 144 razy.

`topology.json` jest źródłem dokładnej adjacencji. `topology.png` jest obrazem
pomocniczym. Dla torusa z joba `3174577` potwierdzono 144 węzły, stopień 4,
576 skierowanych wpisów, brak pętli, pełną wzajemność i spójność grafu.

## 8. Integralność migracji i interpretacja końca runu

W jobie `3174577` zapisano:

```text
send records:                         718560
process-side records:                 718560
unikalne sent event IDs:              718560
unikalne process event IDs:           718560
brakujące/duplikowane zdarzenia:      0
faktycznie przetworzone:              700188
prefetched, nieprzetworzone na końcu: 502
pozostałe w routerze na końcu:        17870
```

`queued_at_end=17870` nie oznacza utraty migrantów. Każde wysłanie ma rekord po
stronie celu; 17 870 rekordów jawnie opisuje stan
`queued_not_dequeued_at_end_of_run`, a 502 stan
`prefetched_not_processed_at_end_of_run`. Jest to zachowana historyczna
semantyka częściowego opróżniania kolejki.

Do analizy signed delay wolno używać tylko faktycznie przetworzonych zdarzeń.
Wartości `null` na końcu runu nie wolno zamieniać na zero. Definicja zapisana
w danych to:

```text
signed_delay_steps = source_step - process_step
```

Ujemna wartość oznacza starszego/opóźnionego migranta, dodatnia migranta ze
źródła wyprzedzającego odbiorcę.

Interwał ustawiony na 5 jest sprawdzany różnicą liczników ewaluacji. Ponieważ
offspring ma rozmiar 4, w tym runie obserwowany odstęp między kolejnymi
migracjami wyniósł konsekwentnie 8 ewaluacji. To istniejąca semantyka, nie
należy jej po cichu przeliczać na pokolenia.

## 9. Aktualne blokery przed kampanią

### 9.1. Silny artefakt pozycji w shardzie

Niezależny audyt wszystkich artefaktów `3174577` wykazał:

- każdy shard zawiera kolejnych 12 ID, czyli przy torusie 12x12 dokładnie jeden
  wiersz topologii;
- we wszystkich 12 shardach najlepsza była ostatnia pozycja `11`;
- w 11 shardach najgorsza była pozycja `0`, w jednym pozycja `1`;
- 9 z 10 globalnie najlepszych wysp miało pozycję `11`, a dziesiąta `10`;
- wszystkie 10 najgorszych miało pozycję `0`, `1` albo `2`;
- korelacja pozycji w shardzie z końcowym fitness: `-0.8809`;
- korelacja pozycji z czasem działania: `+0.8473`;
- średni final fitness spadał od około 313 mln na początku sharda do około
  194 mln na końcu (problem minimalizacyjny).

To bezpośrednio zanieczyszcza wymagane porównanie 10 najlepszych i 10
najgorszych wysp. W tym runie średni signed delay wyniósł około `+112.95` dla
10 najlepszych oraz `-36.03` dla 10 najgorszych, lecz różnicy nie wolno
interpretować jako efektu topologii, dopóki nie oddzielimy jej od kolejności
obsługi sharda.

### 9.2. Batcher używa bardzo małych batchy

Historyczny wynik `3174577`:

```text
requesty:                    287568
fizyczne wywołania GPU:      143197
średnio requestów/batch:     2.008
średnio wierszy/batch:       8.045
docelowy steady batch:       576 wierszy
batche wyzwolone timeoutem:  143197 / 143197
batche wyzwolone rozmiarem:  0
batche z 1-3 requestami:     około 92.5%
suma czasu kerneli GPU:      35.45 s przy 851 s joba
```

Poprawność wyników GPU przeszła, lecz A100 jest niedostatecznie zasilana.
Nie należy po prostu zwiększać timeoutu: zmiana czasu oczekiwania może zmienić
asynchroniczne uporządkowanie i badane delaye. Tuning wymaga osobnej decyzji
eksperymentalnej i nowego canary.

### 9.3. Niespójność metadanych strategii

Faktyczny run jednoznacznie używał `best/plain`:

- argumenty launchera: `best/plain`;
- `param.json`: `best/plain`;
- główna sekcja `scientific_configuration.migration`: `best/plain`;
- wszystkie 718 560 rekordów send: `migrant_selection_strategy=best`.

Jednak osadzony legacy blob
`scientific_configuration.algorithm_configuration.migrant_selection_type`
ma wartość `random` i zawiera starą 10x10 macierz `island_delays`. Nie wpłynęło
to na wykonanie, ale może błędnie sklasyfikować run w przyszłym agregatorze.
Przed kampanią metadane muszą być wewnętrznie jednoznaczne.

### 9.4. Stan lokalnej poprawki z 17 września

Kod lokalny usuwa trzy rozpoznane przyczyny:

- `sha256-ranked-balanced-v1` zastępuje ciągłe grupy ID; mapowanie jest
  deterministyczne, zależne od repeatu i niezależne od topologii;
- `rotating-round-robin-bounded-lead-v1` usuwa stałą pierwszą/ostatnią pozycję
  i ogranicza wyprzedzenie do dwóch kroków, bez synchronizacji między shardami;
- steady batch target wynosi 144 wiersze, timeout 50 ms, a podsumowanie zapisuje
  średnie rozmiary oraz liczby dispatchy `size/timeout/flush`;
- efektywne `scientific_configuration.algorithm_configuration` powstaje z
  aktywnych argumentów. Zawiera właściwe `best/random/maxDistance` i `plain`,
  a nie zawiera nieużywanej legacy macierzy `island_delays`;
- walidator full odrzuca run, jeżeli nie ma ani jednego batcha `size`, średni
  batch ma mniej niż 32 wiersze, ponad 75% batchy ma najwyżej 3 requesty,
  bezwzględna korelacja pozycji z fitness/czasem przekracza 0.5 albo ponad
  połowa shardów ma zwycięzcę na tej samej pozycji.

Lokalnie przechodzą testy kontraktu, pełny dry-run 144 oraz prawdziwy smoke
Ray/NumPy 4 wyspy/2 shardy dochodzący do pętli GA, migracji i finalizacji.
Nie jest to certyfikacja Ray 2.9.3, CuPy ani A100. Hold zostaje zdjęty dopiero
po zaliczonym canary nowego commita i pełnym pilocie, który przejdzie nowe
bramki jakości.

### Decyzja operacyjna

Do czasu targetowej walidacji powyższej poprawki:

- nie zgłaszać kolejnego full;
- nie budować arraya ani automatycznego launchera 1800 runów;
- nie traktować `3174577` jako wyniku do wnioskowania o hipotezach;
- można zachować go jako dowód integracji i materiał diagnostyczny.

## 10. Kolejność ponownej walidacji po poprawce

Po lokalnej poprawce schedulera/metadanych/batchingu:

1. wykonać lokalne testy kontraktu i real-Ray smoke;
2. użytkownik wykonuje commit i push;
3. na Athenie wykonać `git pull --ff-only` i potwierdzić czysty commit;
4. ręcznie zgłosić wyłącznie `submit_study.sh --canary`;
5. sprawdzić `sacct`, oba logi, markery, `validation.json` i artefakty;
6. dopiero po osobnej decyzji użytkownika zgłosić jeden full z canary tego
   samego commita;
7. dla nowego full ponownie zmierzyć zależność fitness/delay od pozycji
   w shardzie oraz rozkład rozmiarów batchy;
8. dopiero po usunięciu konfuzji schedulera projektować kampanię.

Nie wolno automatycznie zgłosić punktu 6 po punkcie 4.

## 11. Eksport dowodów z Atheny

Historyczne joby `3168014`, `3174524` i `3174577` zostały zebrane do:

```text
/net/tscratch/people/plgblaszczykk/islandsEA/exports/athena-study-evidence-3168014-3174524-3174577.tar.gz
```

Rozmiar: około 213 MiB. Oczekiwany SHA-256:

```text
a1fe1e8f3ab8e21cd4e0adc8895d5227f873be9d1c59bf9455a1936327dc9849
```

Archiwum zawiera walidację backendu, canary, full, oba raw runy, katalogi
audit oraz logi SLURM wszystkich trzech jobów.

Historyczne archiwum utworzono na Athenie następująco:

```bash
ROOT="$SCRATCH/islandsEA"
EXPORT="$ROOT/exports"
ARCHIVE="$EXPORT/athena-study-evidence-3168014-3174524-3174577.tar.gz"

mkdir -p "$EXPORT"

ITEMS=(
  "results/athena_benchmark_validation/3168014"
  "results/athena_study_canaries/3174524"
  "results/athena_study_runs/3174577"
  "results/runs/260916/r01_200/205904_53efb97551 12bt-co5ilu5"
  "results/runs/260916/r01_200/211406_c860e3a1ec 144bt-co5ilu5"
  "results/audit/260916_205904_53efb97551"
  "results/audit/260916_211406_c860e3a1ec"
  "logs/slurm/athena-gpu-readiness-3168014.out"
  "logs/slurm/athena-gpu-readiness-3168014.err"
  "logs/slurm/athena-study-canary-3174524.out"
  "logs/slurm/athena-study-canary-3174524.err"
  "logs/slurm/athena-study-full-3174577.out"
  "logs/slurm/athena-study-full-3174577.err"
)

for item in "${ITEMS[@]}"; do
  test -e "$ROOT/$item" || {
    echo "BRAK: $ROOT/$item" >&2
    exit 1
  }
done

tar -C "$ROOT" -czf "$ARCHIVE" -- "${ITEMS[@]}"
sha256sum "$ARCHIVE" > "$ARCHIVE.sha256"
ls -lh "$ARCHIVE" "$ARCHIVE.sha256"
cat "$ARCHIVE.sha256"
```

Pobieranie na Windows PowerShell — używać pełnego hosta, nie aliasu `athena`:

```powershell
$Destination = 'C:\Users\piotr\UMISI\IslandsEA_summer\artifacts\athena\study_3174577'
$Remote = '/net/tscratch/people/plgblaszczykk/islandsEA/exports'
$Name = 'athena-study-evidence-3168014-3174524-3174577.tar.gz'
$Login = 'plgblaszczykk@athena.cyfronet.pl'

New-Item -ItemType Directory -Force -Path $Destination | Out-Null
scp "${Login}:${Remote}/${Name}" $Destination
scp "${Login}:${Remote}/${Name}.sha256" $Destination
```

Weryfikacja przed rozpakowaniem:

```powershell
$Archive = Join-Path $Destination $Name
$HashFile = "$Archive.sha256"
$Expected = (((Get-Content $HashFile -Raw) -split '\s+')[0]).ToUpperInvariant()
$Actual = (Get-FileHash -Algorithm SHA256 $Archive).Hash.ToUpperInvariant()

"Expected: $Expected"
"Actual:   $Actual"

if ($Actual -ne $Expected) {
    throw 'Niezgodna suma SHA-256 — nie rozpakowuj archiwum.'
}
```

Rozpakowanie:

```powershell
tar -xzf $Archive -C $Destination

if ($LASTEXITCODE -ne 0) {
    throw 'Rozpakowanie archiwum nie powiodło się.'
}

Get-ChildItem $Destination
```

Kopia lokalna została zweryfikowana: hash oczekiwany i rzeczywisty były
identyczne, a archiwum rozpakowało katalogi `logs/` i `results/` pod
`artifacts/athena/study_3174577`.

Wszystkie przyszłe wyniki z Atheny również należy odkładać pod:

```text
C:\Users\piotr\UMISI\IslandsEA_summer\artifacts\athena\
```

Nie mieszać ich z artefaktami Aresa.

## 12. Rejestr istniejących dowodów

| Dowód | Stan | Znaczenie |
|---|---|---|
| Lokalna walidacja batch backendu | passed | 170 instancji, 22 016 porównań; nie zastępuje A100 |
| Lokalny real-Ray smoke po poprawce | passed | 4 wyspy, 2 shardy, 20 requestów, 128 wierszy; rotacyjny scheduler i batching bez GPU |
| Dry-run kontraktu po poprawce | passed | 144 wyspy, 12 permutowanych shardów, target 144/50 ms, brak bariery globalnej |
| Historyczny F1 readiness `3167902` | passed dla wcześniejszego F1 | nie waliduje całej czterdziestki ani aktualnego runnera |
| A100 suite `3168014` | passed | 40 benchmarków, NumPy/CuPy, A100 |
| GA canary `3174524` | passed | pełny mały pipeline shardów/batchera/routera/A100 |
| GA full `3174577` | technicznie passed | komplet danych; wykryty artefakt shardów, nie wynik naukowy |

## 13. Typowe problemy

### `squeue: Invalid job id specified`

Job prawdopodobnie już zakończył się i zniknął z aktywnej kolejki. Użyć
`sacct -j <JOB_ID>` i sprawdzić artefakty.

### `libpython3.10.so.1.0: cannot open shared object file`

Przed ręcznym wywołaniem Pythona z venv:

```bash
module load Python/3.10.4
```

### `Could not resolve hostname athena`

Na laptopie używać:

```text
plgblaszczykk@athena.cyfronet.pl
```

W zmiennej PowerShell nie wpisywać backslasha przed `@`.

### Submitter odmawia z powodu Git

Sprawdzić branch, czystość i zgodność z upstream:

```bash
git status --short --branch
git rev-parse HEAD
git rev-parse '@{upstream}'
```

Nie omijać tych bramek i nie zgłaszać joba z dirty checkout.

### `COMPLETED`, ale brak markerów lub `validation.json`

To nie jest sukces. Sprawdzić `.out`, `.err`, katalog wyniku oraz ewentualne
`ray-failure-logs`. Nie ponawiać joba automatycznie.

### Bezpieczny cleanup Ray

Job usuwa wyłącznie własny `/tmp/r<JOB_ID>` i kończy swoją grupę procesów.
Nie przywracać hostowego `ray stop --force`, ponieważ węzeł może być współdzielony.

## 14. Krótka checklista sukcesu

Przed uznaniem runu za zachowany dowód należy mieć wszystkie odpowiedzi `tak`:

1. Czy branch i commit są dokładnie zapisane i checkout był czysty?
2. Czy `sacct` pokazuje `COMPLETED|0:0`?
3. Czy istnieją `.out`, `.err`, `validation.json` i `result_pointer.json`?
4. Czy wszystkie wymagane markery są w stdout?
5. Czy `validation.json` ma `status=passed`, `valid=true`, brak błędów i
   oczekiwany tryb/commit?
6. Czy `environment-check.json` ma `status=passed`?
7. Czy pełny run ma 144 kompletne katalogi wysp?
8. Czy liczba wierszy GPU wynosi dokładnie 1 152 000 dla full?
9. Czy manifesty, `param.json`, `topology.json` i `topology.png` istnieją?
10. Czy artefakty zostały skopiowane lokalnie i zweryfikowane SHA-256?
11. Czy sprawdzono brak artefaktu pozycji w shardzie i rozkład batchy?

Punkty 1-10 oznaczają integralność wykonania i danych. Punkt 11 rozstrzyga,
czy wynik nadaje się do interpretacji naukowej.
