> **Nowy eksport pojedynczego joba (2026-09-19):** wrapper zapisuje
> `run_<job_id>.tar.gz` i SHA-256 w `$SCRATCH/islandsEA/exports`, według
> [wspólnego układu](../hpc_benchmarks/RUN_ARTIFACTS.md). Instrukcje starych
> zbiorczych paczek poniżej są historią; pojedyncze runy pobieraj przez
> `download_run.ps1`, a pełną kampanię ER4/best przez opisany niżej helper.

# Athena GPU: sprawdzony runbook uruchomieniowy i zapis walidacji

Aktualizacja **2026-09-28**: array ER4/best `3201770` ma według przekazanego
`sacct` **120/120 `COMPLETED 0:0`**. Finalizacja z już pobranych bundle
przeszła **lokalnie**, bez ponownego uruchamiania benchmarków; zdalny finalizer
i nowy downloader nie zostały uruchomione na Athenie. Wcześniejsze walidacje
A100: canary `3181809` i full `3185051`.

### Lokalny agregat z już pobranych 120 runów

Katalog `artifacts/run_wyniki/athena/er4_best_3201770/` zawiera już plan,
120 rekordów tasków i 120 przenośnych archiwów runów wraz z SHA-256. Nie trzeba
ponownie uruchamiać benchmarków ani zgłaszać finalizera na Athenie, aby
otrzymać agregat w formule Aresa. Na laptopie, z katalogu tego repozytorium:

```powershell
python -m athena_gpu.finalize_downloaded_er4_best `
  --campaign-dir 'C:\Users\piotr\UMISI\IslandsEA_summer\artifacts\run_wyniki\athena\er4_best_3201770' `
  --array-job-id 3201770
```

Skrypt najpierw sprawdza plan, dokładnie 40×3 rekordów, statusy i proweniencję
runów, walidacje **rzeczywiście obecne wewnątrz** każdego bundle, manifesty
ukończenia oraz SHA-256 każdego archiwum. Potem zapisuje obok katalogu
`er4_best.tar.gz` i `er4_best.tar.gz.sha256`; niczego nie nadpisuje. W tarze
jest jeden katalog `er4_best/` z planem, summary, oryginalnym summary pobrania,
`task_records/`, skopiowanymi z bundle walidacjami, dostępnymi logami oraz
`runs/<benchmark>/repeat-<n>/run_<rzeczywisty_JOB_ID>.tar.gz[.sha256]`.
Wszystkie 120 wewnętrznych tarów jest przenoszone bajt w bajt, bez zmiany
metryk naukowych. Summary rozróżnia dowód zakończenia z manifestów runów od
nieobecnego w lokalnym źródle, niezależnego zrzutu `sacct`; brakujące logi
wymienia jawnie. Oryginalny katalog pobrania pozostaje bez zmian.

Wykonana lokalna finalizacja `3201770`: **120/120 valid**, 120 archiwów + 120
checksumów, 120 rekordów, 120 walidacji i 240 dostępnych snapshotów logów
w jednym katalogu `er4_best/`. Plik wynikowy:
`artifacts/run_wyniki/athena/er4_best.tar.gz` (21 925 958 201 bajtów),
SHA-256 `5def55dcf6d3e7b05f95c1fb3f5d9a82e4548be46ea39f01615aa4bed220b90c`.
Zewnętrzny hash, lista członków tara i SHA-256 wszystkich 120 wewnętrznych
archiwów względem ich checksumów zostały sprawdzone po zapisaniu.

## Produkcyjna partia ER4 / best / 40 × 3

Launcher zgłasza dokładnie jeden
array SLURM `1-120%3`. Każdy element jest niezależnym pełnym runem: jedna A100,
16 CPU, 144 logiczne wyspy na 12 shardach, 8000 ewaluacji/wyspę, populacja 16,
potomkowie 4, pięciu migrantów co 5 ewaluacji, `er4`, `best/plain`, D=200,
seed bazowy 20260912, seed instancji binarnej 20260511. Wszystkie 30 funkcji
ciągłych i 10 binarnych mają po trzy powtórzenia. D=200 dla CEC jest
rozszerzeniem IslandsEA, nie oficjalną instancją CEC2014.

Mapowanie jest stałe: task `3*i+1`, `3*i+2`, `3*i+3` to powtórzenia 1, 2, 3
benchmarku o indeksie `i` (od zera) w `BENCHMARKS`. Pierwszy task to
`r01_elliptic`/1, ostatni `b10_maxcut_ring`/3. Przed submittem skrypt
kontroluje liczbę funkcji i hash zatwierdzonego grafu ER4
`469cc283543dcc60d5bf8f07db2eabfb12cab34637f4a6d26bca51d07f85cccc`.
Nie generuje grafu i nie zmienia seeda w zależności od pozycji w arrayu:
powtórzenia używają repeat-base 20260912, 21260912, 22260912.

W przyszłych kampaniach, po commit/push i pull wykonanych przez użytkownika,
trzeba najpierw wskazać **rzeczywiście przydzieloną partycję i konto CPU-only
z dostępem do tego samego SCRATCH** (nie zgadywać nazw):

```bash
export ATHENA_FINALIZER_PARTITION='<zatwierdzona-partycja-CPU>'
export ATHENA_FINALIZER_ACCOUNT='<zatwierdzone-konto-CPU>'
cd "$HOME/islandsEA_student_fork"
bash athena_gpu/submit_production_er4_best_120.sh
```

Submitter na login node zgłasza array GPU oraz **jeden CPU-only finalizer** z
`--dependency=afterany:<ARRAY_ID>`. Nie ma canary, bramki określonego commita,
retry ani dodatkowego joba GPU. Athena jest według dokumentacji Cyfronetu
klastrem GPU-only; nie kierować ciężkiego pakowania na A100 bez GPU ani nie
wykonywać go na login node. Bez uprawnionego zasobu CPU nowy submitter
zatrzymuje się **przed** zgłoszeniem arraya.
Commit i stan Git są zapisywane jako proweniencja. Nie robić `git pull` ani
lokalnych zmian w checkoutcie na Athenie, dopóki cały array nie zakończy
pracy: kolejne elementy startują później i mogłyby odczytać inny kod.
Limit to 2 godziny / 2 GPUh
na element (górna granica 240 GPUh całego arraya), najwyżej trzy elementy
jednocześnie. Każdy element ma osobny numeryczny `SLURM_JOB_ID`, katalog
`$SCRATCH/islandsEA/results/athena_production_er4_best_120/<JOB_ID>/`,
`validation.json`, logi `athena-er4-best-120-<ARRAY_ID>_<TASK_ID>.{out,err}`
oraz `exports/run_<JOB_ID>.tar.gz` z SHA-256. Tylko `COMPLETED 0:0`,
`validation.json` z `status=passed`/`valid=true` i markery
`ATHENA_STUDY_FULL_RUN_OK=1`, `ATHENA_STUDY_JOB_OK=1` oraz
`ATHENA_ER4_BEST_TASK_OK=<TASK_ID>` oznaczają zaliczony
element; samo pojawienie się archiwum nie wystarcza. Walidator sprawdza
faktyczną adjacencję i proweniencję ER4, budżet, seedy, migracje, metryki
GPU i komplet wyników.

Podczas submitu powstaje plan 120 konfiguracji. Po sukcesie każdego elementu
skrypt niezależnie weryfikuje przenośny bundle i zapisuje rekord zadania oraz
twarde dowiązanie archiwum i SHA-256 w:

```text
$SCRATCH/islandsEA/campaigns/er4_best_<ARRAY_ID>/
├── campaign_plan.json
├── tasks/task-001.json ... task-120.json
└── runs/<benchmark>/repeat-<1|2|3>/run_<JOB_ID>.tar.gz[.sha256]
```

Dowiązania dotyczą tylko plików na tym samym SCRATCH; kanoniczne
`$SCRATCH/islandsEA/exports/run_<JOB_ID>.tar.gz` pozostają dostępne dla
wspólnego `download_run.ps1`.

Finalizer czyta faktyczny `sacct` (`JobIDRaw`, `JobID`, `State`, `ExitCode`),
plan, dokładnie 120 rekordów, osobny `validation.json` dla każdego runa,
głęboko weryfikuje bundle i jego SHA-256. Nie uzupełnia brakujących walidacji
ani logów. Dostępne logi włącza do agregatu, brakujące wymienia w
`campaign_summary.json`. Dopiero po pełnym sukcesie tworzy w katalogu kampanii
`er4_best_<ARRAY_ID>.tar.gz` i `.tar.gz.sha256`. Jedynym katalogiem w środku
jest `er4_best_<ARRAY_ID>/` z planem, podsumowaniem, `sacct.txt`, rekordami,
kopiami 120 rzeczywistych walidacji, dostępnymi logami oraz 120 niezmienionymi
archiwami `runs/<benchmark>/repeat-<n>/run_<rzeczywisty_JOB_ID>.tar.gz[.sha256]`.
To jest dodatkowy duży plik na SCRATCH, więc finalizer sprawdza wolne miejsce.
Pojedynczy bundle zachowuje wspólny z Aresem kontrakt `logs/`, `metrics/`,
`results/`, `identifier.txt`, `metadata.json`.

Dla **już obliczonego** `3201770` nie zgłaszać ponownie 120 benchmarków.
Po potwierdzeniu dozwolonego zasobu CPU użytkownik może z login node zgłosić
sam finalizer (bez zależności do historycznie zakończonego arraya):

```bash
export ATHENA_FINALIZER_PARTITION='<zatwierdzona-partycja-CPU>'
export ATHENA_FINALIZER_ACCOUNT='<zatwierdzone-konto-CPU>'
bash athena_gpu/submit_finalize_production_er4_best_120.sh --existing 3201770
```

Gdyby CPU-only na współdzielonym SCRATCH nie było dostępne, zatrzymać się i
uzgodnić zasób z administracją; **nie** odpalać 120 runów ponownie ani nie
uruchamiać kilkudziesięciogigabajtowej kompresji na login node. Dla
przyszłego arraya osobne zgłoszenie finalizera, gdyby było potrzebne, to
`bash athena_gpu/submit_finalize_production_er4_best_120.sh --afterany
<ARRAY_ID>`. Normalnie nowy launcher zgłasza go automatycznie.

Po zakończeniu sprawdzić oba joby przez `sacct -X -j <ID> -P
--format=JobID,State,ExitCode,Elapsed,NodeList` (wersja Slurma na Athenie nie
obsługuje pól `ArrayJobID`/`ArrayTaskID`). Na laptopie wybrać **jedno** z
poniższych poleceń:

```powershell
.\athena_gpu\download_production_er4_best_120.ps1 -ArrayJobId 3201770
# Albo od razu pobrać, rozpakować i sprawdzić 120 wewnętrznych sum:
.\athena_gpu\download_production_er4_best_120.ps1 -ArrayJobId 3201770 -Extract
```

Jeden `scp` pobiera **tylko** `er4_best_3201770.tar.gz` i `.sha256` obok siebie
w `artifacts/run_wyniki/athena/`; kontrola zewnętrznego SHA-256 jest zawsze
obowiązkowa. `-Extract` dodatkowo sprawdza plan, summary, 120 rekordów,
walidacji, archiwów i ich SHA-256 w
`artifacts/run_wyniki/athena/er4_best_3201770/`. Skrypt nie nadpisuje
istniejących dwóch plików ani katalogu; bez `-Extract` może pobrać tar obok
wcześniejszego katalogu bez jego zmiany. Po pierwszym pobraniu samo
`-Extract` przez ten downloader nie jest trybem „rozpakuj lokalny plik”:
użyć go przy pierwszym pobraniu albo wskazać inny `-Destination`. Nie mieszać
wyników z Aresem. ID arraya nie jest ID każdego runa.

## Produkcyjna partia ER4 / random / 40 × 3

Wariant `random` zmienia **wyłącznie wybór migrantów** względem ER4/best.
Zostają te same: zamrożony graf ER4 i hash adjacencji, kolejność 40 benchmarków,
D=200, 144 wyspy, 8000 ewaluacji/wyspę, populacja 16, potomkowie 4, grupa i
interwał migracji 5/5, akceptacja `plain`, powtórzenia 1–3 i seed bazowy
20260912. Preflight porównuje SHA-256 kolejności benchmarków z kampanią
ER4/best `3201770`. Bez canary, bramki commita i automatycznego retry. Z repo
na login node użytkownik uruchamia **jedno polecenie** (nie uruchamiać go lokalnie):

```bash
bash athena_gpu/submit_production_er4_random_120.sh
```

Nie zmieniać checkoutu na Athenie (`git pull` ani edycji plików) do zakończenia
całego arraya: późniejsze taski korzystają z tego samego katalogu kodu.

Submitter sprawdza graf i wszystkie 40 instancji, zgłasza jeden array GPU
`1-120%3` (A100 + 16 CPU, maksymalnie 2 godziny i 2 GPUh na element; górna
granica 240 GPUh), tworzy plan `campaigns/er4_random_<ARRAY_ID>/campaign_plan.json`
przy zatrzymanym arrayu, po czym go zwalnia. Każdy task ma osobny
`SLURM_JOB_ID`, `results/athena_production_er4_random_120/<JOB_ID>/validation.json`,
log `logs/slurm/athena-er4-random-120-<ARRAY_ID>_<TASK_ID>.{out,err}` i
`exports/run_<JOB_ID>.tar.gz[.sha256]`; w katalogu kampanii pojawia się rekord
tasku i dowiązanie do tego samego bundle. Zgodność strategii `random` jest
sprawdzana w aktywnym wywołaniu GA, efektywnych metadanych, walidacji i planie.

Ten launcher **nie** zgłasza dodatkowego finalizera: nie zakłada niepotwierdzonej
partycji CPU-only na Athenie ani nie pakuje dziesiątek GB na login node. Po
zakończeniu sprawdzić `sacct -X -j <ARRAY_ID> -P
--format=JobID,State,ExitCode,Elapsed,NodeList`. Dopiero dla kompletnej kampanii
na laptopie, z katalogu tego repozytorium:

```powershell
.\athena_gpu\download_production_er4_random_120.ps1 -ArrayJobId <ARRAY_ID>
python -m athena_gpu.finalize_downloaded_er4 `
  --campaign-dir 'C:\Users\piotr\UMISI\IslandsEA_summer\artifacts\run_wyniki\athena\er4_random_<ARRAY_ID>' `
  --array-job-id <ARRAY_ID> --strategy random
```

Downloader używa jednego połączenia `scp -r`, nie nadpisuje istniejącego
katalogu i weryfikuje 120 pobranych SHA-256. Lokalny finalizer dodatkowo
sprawdza plan, rekordy, walidacje i zawartość każdego bundle; dopiero po
pełnym sukcesie tworzy `artifacts/run_wyniki/athena/er4_random.tar.gz` i
`.tar.gz.sha256`, z jednym katalogiem `er4_random/` w formule Aresa. Wymaga
wolnego miejsca na drugi zestaw ~22 GB danych; rozmiar rzeczywisty zależy od
wyników. Nie dopisuje nieobecnego `sacct` ani logów. Oryginalne archiwa i
metryki pozostają niezmienione.

## Przygotowana partia ER4 / maxDistance / 40 × 3

Wariant `maxDistance` zachowuje zamrożony graf ER4, tę samą kolejność 40
benchmarków, D=200, 144 wyspy, budżet 8000 ewaluacji na wyspę, populację
16/4, migrację 5/5, `plain`, seedy i trzy powtórzenia. Zmienia wyłącznie
strategię **wyboru** migrantów. Naukowa nazwa jest dokładnie `maxDistance`;
w nazwach katalogów i logów używamy `maxdistance`, zgodnie z Ares.

Launcher `athena_gpu/submit_production_er4_maxdistance_120.sh` zgłasza jeden
array GPU `1-120%3` (A100, 16 CPU, 2 godziny na element, maksymalnie 240 GPUh),
zapisuje plan `campaigns/er4_maxdistance_<ARRAY_ID>/campaign_plan.json` przed
zwolnieniem arraya i nie zgłasza canary, retry ani dodatkowego finalizera.
Każdy element ma własny rzeczywisty `SLURM_JOB_ID`, walidację w
`results/athena_production_er4_maxdistance_120/<JOB_ID>/validation.json`,
archiwum `exports/run_<JOB_ID>.tar.gz[.sha256]` i rekord kampanii. Żaden
element nie przepisuje naukowych metryk.

**Nie wdrażać nowego kodu na Athenie, dopóki aktywny array ER4/random
`3205860` się nie zakończy**: późniejsze taski korzystają z bieżącego checkoutu.
Po zakończeniu, sprawdzeniu wszystkich statusów i ręcznym przygotowaniu
nowego commita przez użytkownika, komenda na login node będzie:

```bash
bash athena_gpu/submit_production_er4_maxdistance_120.sh
```

Po zakończeniu kampanii sprawdzić `sacct -X -j <ARRAY_ID> -P
--format=JobID,State,ExitCode,Elapsed,NodeList`. Pobieranie na laptopie:

```powershell
.\athena_gpu\download_production_er4_maxdistance_120.ps1 -ArrayJobId <ARRAY_ID>
python -m athena_gpu.finalize_downloaded_er4 `
  --campaign-dir 'C:\Users\piotr\UMISI\IslandsEA_summer\artifacts\run_wyniki\athena\er4_maxdistance_<ARRAY_ID>' `
  --array-job-id <ARRAY_ID> --strategy maxDistance
```

Downloader korzysta z jednego `scp -r`, nie nadpisuje pobranego katalogu i
sprawdza SHA-256 wszystkich 120 wewnętrznych archiwów. Lokalny finalizer
wymaga kompletnego planu, rekordów, walidacji i bundle; po sukcesie tworzy
`artifacts/run_wyniki/athena/er4_maxdistance.tar.gz` oraz `.sha256` z jednym
katalogiem `er4_maxdistance/`. Nie deklaruje brakujących logów jako obecnych.
Do pobrania i finalizacji potrzebne jest odpowiednie wolne miejsce lokalne;
można wskazać większy dysk przez `-Destination`.

Ten dokument utrwala działającą procedurę dla Atheny, wyniki wykonanych
walidacji oraz znane ograniczenia. Dotyczy kodu z `athena_gpu/`. Nie jest instrukcją dla
Aresa i nie wolno przenosić tutaj profilu CPU Aresa.

Najważniejszy stan na 2026-09-19:

- backend wszystkich 40 benchmarków przeszedł pełną walidację NumPy/CuPy na
  A100;
- poprawiony canary `3181809` i pełny run `3185051` przeszły na A100 na
  czystym commicie `0547d5917459be100ff8860875b2a906ab8b0f08`;
- pełny run F1/D=200/144 wyspy zachował komplet wymaganych danych i przeszedł
  nowe bramki batchingu, schedulera, migracji oraz proweniencji;
- historyczny job `3174577` pozostaje wyłącznie dowodem integracji: miał silną
  zależność wyniku od pozycji wyspy w shardzie, małe batche i niespójne
  metadane. Tych problemów nie stwierdzono w `3185051`;
- targetowa walidacja runnera jest zakończona. Nie oznacza to automatycznej
  zgody na zgłoszenie kampanii 1800 runów: plan kampanii i sposób jej
  porcjowania nadal wymagają osobnej decyzji użytkownika;
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

### 6.1. Zamrożony run porównawczy z trzema powtórzeniami

Do porównania z równoległym pilotem Aresa służy wyłącznie:

```bash
bash athena_gpu/submit_frozen_torus3.sh
```

Submitter nie wymaga canary, ID canary, konkretnego commita, czystego drzewa
ani zgodności z upstreamem. Sprawdza tylko zgodność naukowej części
`pilot_run/pilot_spec.json` z zamrożonym kontraktem, po czym zgłasza jeden
SLURM array `1-3%3`, bez zależności, retry i finalizera. Aktualny commit oraz
stan dirty są zachowywane wyłącznie jako proweniencja. Każdy element ma jedną
A100, 16 CPU, limit 2 godzin i wykonuje jeden repeat:

| Repeat | Base seed runnera | Seed wyspy `i` |
|---:|---:|---:|
| 1 | 20260912 | `20260912 + i` |
| 2 | 21260912 | `21260912 + i` |
| 3 | 22260912 | `22260912 + i` |

Wszystkie trzy używają tej samej instancji benchmarku i `instance-seed`
20260511. Numer repeatu wpływa na RNG wysp oraz deterministyczne mapowanie
wysp na shardy, nie zmienia torusa ani instancji funkcji celu. Każdy element
zapisuje osobne `validation.json` i przenośną paczkę
`$SCRATCH/islandsEA/exports/run_<element_SLURM_JOB_ID>.tar.gz`.

Maksymalny koszt całego arraya wynosi 6 GPUh. Zgłoszenie jest ręczne.
Historyczny `3185051` pozostaje poprawnym pojedynczym repeatem 1, ale zamrożony
komplet porównawczy uruchamia wszystkie trzy repeaty w jednym formacie
artefaktów.

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

### Targetowa ponowna walidacja: joby 3181809 i 3185051

Poprawiony runner sprawdzono na czystym commicie:

```text
0547d5917459be100ff8860875b2a906ab8b0f08
```

Canary `3181809` zakończył się `COMPLETED|0:0` w 42 s, wypisał wszystkie
markery sukcesu i zapisał `status=passed`, `valid=true`, `errors=[]`.
Na A100 wykonał 1536 wierszy w 30 wywołaniach backendu. Średni batch miał
51.2 wiersza i 11.6 requestu; 28 z 30 batchy uruchomił próg rozmiaru, a tylko
3.33% batchy zawierało najwyżej trzy requesty. Migracje miały 840 rekordów
send i 840 odpowiadających rekordów terminalnych, bez braków i duplikatów.

Pełny pilot `3185051` jest normalnym runem kontraktu 144 wysp:

| Pole | Wynik |
|---|---|
| Job | `3185051` |
| Commit | `0547d5917459be100ff8860875b2a906ab8b0f08` |
| Węzeł | `t0003` |
| SLURM | `COMPLETED`, `0:0` |
| Czas | 00:13:59 (839 s) |
| TotalCPU | 01:23:26 |
| MaxRSS | 12 261 828 KiB, około 11.7 GiB |
| GPU | NVIDIA A100-SXM4-40GB |
| Raw run | `results/runs/260919/r01_200/134902_dafd553493 144bt-co5ilu5` |

Walidacja pełnego pilota zapisała:

```text
status=passed
valid=true
errors=[]
row_count=1152000
backend_calls=13056
średnio requestów/batch=22.026
średnio wierszy/batch=88.235
batche size/timeout=739/12317
odsetek batchy z <=3 requestami=0.245%
korelacja pozycja-final fitness=+0.0142
korelacja pozycja-wall time=+0.0122
maksymalny udział tej samej pozycji wśród zwycięzców shardów=0.25
```

Wszystkie pełne bramki zostały spełnione: co najmniej jeden batch `size`,
średnio co najmniej 32 wiersze/batch, najwyżej 75% małych batchy, obie
bezwzględne korelacje najwyżej 0.5 i najwyżej połowa zwycięzców shardów na tej
samej pozycji. Progi są zapisane w manifeście pod kluczem
`athena_plan.full_run_quality_gates`; odczyt `athena_plan.quality_gates`
zwróci `None`, ponieważ taki klucz nie istnieje.

Efektywne metadane są jednoznaczne: `best/plain`, brak `island_delays`, torus
12x12, repeat 1, seed 20260912, F1/D=200 oraz backend
`athena-gpu-sharded`. Migracje zachowały 718 560 send i 718 560 terminalnych
process records, bez braków i duplikatów. `queued_at_end=2175` jest jawnie
zapisywane jako `queued_not_dequeued_at_end_of_run`, zgodnie z opisaną niżej
semantyką końca runu; nie jest utratą rekordu.

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

## 9. Historyczne blokery i wynik ich weryfikacji

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

### 9.4. Poprawka z 17 września zweryfikowana 19 września

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

Oprócz testów lokalnych, dry-runu 144 i smoke Ray/NumPy poprawka przeszła
targetową weryfikację Ray 2.9.3, CuPy 10.6.0 i A100 w canary `3181809` oraz
pełnym pilocie `3185051`. Pełny pilot przeszedł wszystkie wymienione wyżej
bramki jakości. Hold związany z artefaktem pozycji, batchingiem i niespójnymi
metadanymi jest zdjęty dla commita `0547d5917459be100ff8860875b2a906ab8b0f08`.

### Decyzja operacyjna

Po targetowej walidacji:

- nie traktować `3174577` jako wyniku do wnioskowania o hipotezach;
- `3185051` spełnia kontrakt normalnego runu i może zostać zachowany jako
  pierwszy wynik konfiguracji F1/D=200/torus/best/plain/repeat 1;
- nie zgłaszać automatycznie kolejnych runów ani arraya; porcjowanie kampanii,
  limity i procedura wznowień wymagają osobnego zatwierdzenia użytkownika;
- najpierw ręcznie spakować, pobrać i zweryfikować dowody `3181809` oraz
  `3185051` według sekcji 11. Te joby wykonano przed wdrożeniem nowego
  automatycznego eksportu `run_<job_id>.tar.gz`.

## 10. Zakończona ponowna walidacja po poprawce

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

Kroki 1-7 wykonano i zakończono sukcesem w jobach `3181809` oraz `3185051`.
Krok 8 oznacza osobny etap projektowania kampanii, a nie automatyczne
zgłoszenie następnych jobów.

## 11. Eksport dowodów z Atheny

### Canary 3181809 i pełny pilot 3185051

Oba joby wykonano na commicie `0547d59`, który nie zawierał jeszcze nowego
automatycznego eksportera pojedynczego runu. Należy więc jednorazowo utworzyć
na Athenie wspólne archiwum dowodowe:

```bash
ROOT="$SCRATCH/islandsEA"
EXPORT="$ROOT/exports"
ARCHIVE="$EXPORT/athena-study-evidence-3181809-3185051.tar.gz"

mkdir -p "$EXPORT"

ITEMS=(
  "results/athena_study_canaries/3181809"
  "results/athena_study_runs/3185051"
  "results/runs/260918/r01_200/181034_5a05bfa7ca 12bt-co5ilu5"
  "results/runs/260919/r01_200/134902_dafd553493 144bt-co5ilu5"
  "results/audit/260918_181034_5a05bfa7ca"
  "results/audit/260919_134902_dafd553493"
  "logs/slurm/athena-study-canary-3181809.out"
  "logs/slurm/athena-study-canary-3181809.err"
  "logs/slurm/athena-study-full-3185051.out"
  "logs/slurm/athena-study-full-3185051.err"
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

Archiwum i plik SHA-256 należy pobrać na laptop do
`artifacts/athena/study_3185051`, zweryfikować przed rozpakowaniem i zachować
obok poprzednich dowodów. Procedura PowerShell niżej jest taka sama; trzeba
podmienić `$Destination` oraz `$Name`.

Eksport wykonano i sprawdzono lokalnie. Archiwum ma 207 715 773 bajty, a jego
SHA-256 wynosi:

```text
8979010d2d0edcae0e1b6e9fde77f3b14e2dcae9a8c43b5d6c4047741f6a9bfd
```

Hash z Atheny i hash lokalny są identyczne. Rozpakowana kopia znajduje się w:

```text
C:\Users\piotr\UMISI\IslandsEA_summer\artifacts\athena\study_3185051
```

Kontrola lokalna potwierdziła 12/12 katalogów metryk wysp dla canary,
144/144 dla full, zero brakujących wymaganych plików głównych, per-island i
`metrics/athena`, wszystkie markery sukcesu oraz brak komunikatów błędu poza
zwykłym ładowaniem modułów i startem Ray.

### Historyczne joby 3168014, 3174524 i 3174577

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
| GA canary `3181809` | passed | poprawiony scheduler, batching i metadane na A100; commit `0547d59` |
| GA full `3185051` | passed | 144 wyspy; wszystkie bramki jakości i integralności zaliczone; normalny wynik F1/torus/best/repeat 1 |

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

Ta sekcja dotyczy starszego `submit_study.sh`. Zamrożony
`submit_frozen_torus3.sh` nie ma bramki branch/clean/upstream/commit.
W starszym submitterze sprawdzić branch, czystość i zgodność z upstream:

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
