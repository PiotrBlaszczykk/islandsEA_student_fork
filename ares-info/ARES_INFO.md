# Ares / Cyfronet — stan środowiska i plan uruchomień IslandsEA

Ostatnia aktualizacja: **2026-09-13**  
Użytkownik Aresa: `plgblaszczykk`  
Cel dokumentu: trwały handoff dla kolejnych sesji pracujących nad uruchomieniem benchmarków IslandsEA na Aresie.

## 1. Stan w skrócie

- Podstawowy test SLURM + Python + venv + Ray zakończył się sukcesem: job `21045868`, `COMPLETED`, `ExitCode=0:0`.
- Aktywna i potwierdzona ścieżka wykonania to **Ray na SLURM**, nie RabbitMQ i nie lokalny compute.
- Repo na Aresie było czyste na branchu `summer_benchmarks`, commit `40f1d3e7efe678ec32c6595dae847a393a9a1dd9` (`added refined benchmarks`).
- Dostępne konto produkcyjne CPU: `plglscclass26-cpu`; domyślna partycja: `plgrid`.
- Działający venv: `/net/people/plgrid/plgblaszczykk/venvs/islands-ray`.
- Lokalny `main_codebase` ma przygotowany profil `hpc_benchmarks/run_ares_200.sh`: 9 × 48 CPU, 401 wymaganych CPU Ray, osobny CPU drivera, preflight przed startem Ray i cache Matplotlib rozgrzewany na każdym węźle. Zmiany wymagają jeszcze commit/push/pull i canary na Aresie; nie są wynikiem potwierdzonego joba 200-wyspowego.
- Pełnej kampanii 1800 uruchomień **nie należy jeszcze wysyłać**. Najpierw trzeba:
  1. wykonać walidację i małe pilotaże nowego launchera na Aresie;
  2. ustalić wspólną liczbę wysp / zestaw topologii;
  3. zmierzyć wielkość i liczbę plików pełnego pilota w przygotowanym pipeline `$SCRATCH`;
  4. wykonać kilka reprezentatywnych pełnowymiarowych pilotów i dopiero z nich wyznaczyć czas oraz CPU-hours.

Smoke test sprawdza wyłącznie poprawność infrastruktury. Jego projekcja `8.4 CPUh` dla całej kampanii jest matematycznie poprawna dla siedmiosekundowego smoke'a, ale **nie jest estymacją benchmarków**.

## 2. Źródła tego raportu

- `main_codebase/ares_diagnostics.txt` — diagnostyka wygenerowana na `login01` 2026-09-12 o 20:07 CEST;
- `main_codebase/job_cost_smoke.json` — koszt joba `21045868`;
- bieżący `AGENTS.md`, `hpc_benchmarks/README.md`, `hpc_benchmarks/run_ares.sh` i kod runtime z brancha `summer_benchmarks`;
- wcześniejszy log udanego smoke testu przekazany w sesji.

Informacje o kolejce, fairshare, dostępności węzłów i użyciu dysku są migawką z 2026-09-12. Przed dużą serią trzeba je sprawdzić ponownie.

## 3. Stałe ścieżki i workflow

### Ares

```text
repo:       /net/people/plgrid/plgblaszczykk/islandsEA_student_fork
venv:       /net/people/plgrid/plgblaszczykk/venvs/islands-ray
scratch:    /net/afscra/people/plgblaszczykk/islandsEA
wyniki raw: $SCRATCH/islandsEA/results/runs
pilot:      $SCRATCH/islandsEA/results/pilot_runs
audit:      $SCRATCH/islandsEA/results/audit
logi SLURM: $SCRATCH/islandsEA/logs/slurm
diagnostyka:$SCRATCH/islandsEA/results/diagnostics
```

### Laptop

```text
repo:      C:\Users\piotr\UMISI\IslandsEA_summer\main_codebase\islandsEA_student_fork
wyniki:    C:\Users\piotr\UMISI\IslandsEA_summer\artifacts
ten raport:C:\Users\piotr\UMISI\IslandsEA_summer\main_codebase\ARES_INFO.md
```

Zakładany przepływ:

1. modyfikacja i testy statyczne na laptopie, bez lokalnych benchmarków;
2. `git push` na laptopie;
3. `git pull --ff-only` na Aresie;
4. `sbatch` na Aresie;
5. finalizacja i spakowanie wyniku na `$SCRATCH`, potem pobranie przez `pilot_run/download_pilot.ps1` lub WinSCP do lokalnego `artifacts`;
6. potwierdzenie kompletności/checksum przed usuwaniem czegokolwiek z Aresa.

Finalizowany pilot pobiera się z PowerShella na laptopie:

```powershell
cd C:\Users\piotr\UMISI\IslandsEA_summer\main_codebase\islandsEA_student_fork
.\pilot_run\download_pilot.ps1 -JobId ARRAY_JOB_ID
```

Helper odczytuje zdalny `$SCRATCH`, zapisuje pod
`C:\Users\piotr\UMISI\IslandsEA_summer\artifacts\pilot_runs\` i wymaga trzech
poprawnych checksum oraz `pilot_summary.json` z trzema zaliczonymi próbami.

Aktualny launcher nie zapisuje danych eksperymentalnych w repo ani `~/artifacts`; wspólny kontrakt `hpc_benchmarks/ares_storage.sh` kieruje je pod `$SCRATCH/islandsEA`, patrz sekcja 10.

## 4. System, SLURM i sprzęt

### Potwierdzone wersje

| Element | Wartość |
|---|---|
| Host logowania | `login01.ares.cyfronet.pl` |
| System | Linux, kernel `4.18.0-553.144.1.el8_10.x86_64` |
| SLURM | `23.11.6` |
| Selekcja zasobów | `select/cons_tres`, `CR_CPU_MEMORY` |
| Maksymalny job array | `20001` elementów na poziomie klastra |
| Standardowy węzeł CPU | 48 fizycznych rdzeni, `ThreadsPerCore=1` |
| RAM standardowego węzła | `184800 MB` raportowane przez SLURM |
| Przykładowy CPU | Intel Xeon Cascade Lake |

Login node pokazał 12 CPU, ale nie jest miejscem wykonywania obliczeń. Smoke działał na compute node `ac0640`, który ma 48 rdzeni i 184800 MB RAM.

### Konto i limity użytkownika

- Domyślne konto: `plglscclass26-cpu`.
- Istnieje też asocjacja `plglscclass26-gpu`, ale obecny workload IslandsEA jest CPU-only; nie należy rezerwować GPU.
- QOS asocjacji: `normal`.
- `MaxSubmitJobs=1000` dla asocjacji CPU i GPU.
- `MaxJobs`, `GrpTRES`, `GrpTRESMins` i podobne limity nie zostały pokazane jako ustawione.
- To **nie mówi**, ile CPU-hours pozostało w grancie. Pozostały budżet trzeba sprawdzić w portalu/grancie PLGrid albo właściwym narzędziem rozliczeniowym.
- Maksymalny rozmiar tablicy w klastrze (`20001`) nie znosi limitu `MaxSubmitJobs=1000`. Nie zakładać, że tablica 1800 tasków przejdzie. Kampanię należy wysyłać falami znacznie mniejszymi niż 1000.
- W chwili diagnostyki kolejka użytkownika była pusta.
- Fairshare konta CPU wynosił `0.090663`. To zmienna migawka wpływająca na priorytet, nie gwarantowany czas oczekiwania.

### Dostępne partycje dla `plglscclass26-cpu`

| Partycja | Dostęp | MaxTime | MaxNodes | Zastosowanie |
|---|---:|---:|---:|---|
| `plgrid` | tak, domyślna | 3 dni | bez jawnego limitu | właściwa produkcja i pełne piloty |
| `plgrid-now` | tak | 12 h | bez jawnego limitu | krótsze pilne joby; używać świadomie |
| `plgrid-testing` | tak | 1 h | 2 | walidacja i małe testy, nie 150–200 wysp |
| `plgrid-long` | niepotwierdzony/brak konta na liście | 7 dni | — | nie planować na nim kampanii |
| `plgrid-bigmem` | brak konta CPU na liście | 3 dni | — | niepotrzebne dla obecnej konfiguracji |

Domyślny czas partycji to tylko 15 minut. Każdy benchmark powinien jawnie podawać `--time`.

### Pamięć i billing

- `plgrid` ma `DefMemPerCPU=3850 MB` i wagi billingowe `cpu=1,mem=0.265G`.
- `hpc_benchmarks/run_ares.sh` jawnie prosi o `--mem-per-cpu=2G`.
- Przy 2 GB/CPU komponent CPU powinien dominować billing; do roboczych estymacji używamy `AllocCPUS × Elapsed`.
- Nie zwiększać pamięci „na zapas” bez pomiaru, bo może podnieść TRES billing.
- Smoke nie dostarczył wiarygodnego `MaxRSS` (`0`/brak danych). Pełny pilot musi dostarczyć pomiar pamięci przez `sacct`.

## 5. Python i venv

Aktywacja:

```bash
module load python/3.10.4-gcccore-11.3.0
source /net/people/plgrid/plgblaszczykk/venvs/islands-ray/bin/activate
```

Potwierdzone wersje:

| Pakiet | Wersja |
|---|---:|
| Python | `3.10.4` |
| Ray | `2.9.3` |
| jMetalPy | `1.5.5` |
| NumPy | `1.21.4` |
| SciPy | `1.7.3` |
| scikit-learn | `1.1.3` |
| pandas | `1.3.4` |
| matplotlib | `3.5.0` |
| setuptools | `80.10.2` |
| wheel | `0.48.0` |
| packaging | `21.3` |

`setuptools<81` jest celowe dla Ray 2.9.x, ponieważ Ray korzysta jeszcze z `pkg_resources`. Ostrzeżenie o deprecjacji `pkg_resources` w smoke teście było niegroźne.

`pip check` nie jest obecnie czysty:

```text
wheel 0.48.0 has requirement packaging>=24.0, but packaging 21.3 is installed
```

To konflikt narzędzia budującego, a nie zaobserwowany błąd runtime — smoke przeszedł. `packaging==21.3` jest przypięte w requirements projektu, więc nie należy go ślepo podnosić. Przed zamrożeniem środowiska należy dobrać zgodną wersję `wheel`, uruchomić `pip check`, walidację 17 testów i małe piloty, a następnie zachować `pip freeze`. Nie tworzyć ponownie venva tylko z powodu dodania benchmarków.

## 6. Potwierdzony smoke test

| Pole | Wartość |
|---|---|
| Job | `21045868` (`islandsea-smoke`) |
| Partycja / konto | `plgrid` / `plglscclass26-cpu` |
| Stan | `COMPLETED`, `ExitCode=0:0` |
| Węzeł | `ac0640` |
| Alokacja | 2 CPU, 4 GB RAM |
| Wall time | 7 s |
| Allocated CPU time | 14 CPU-sekund = `0.0038889 CPUh` |
| `TotalCPU` | 4.613 s; wynik nie służy do oceny efektywności benchmarku |
| Wynik funkcjonalny | `SMOKE_TEST_OK`; zdalny task Ray zwrócił wynik |

Ray korzystał z lokalnego katalogu tymczasowego węzła:

```text
/tmp/plgblaszczykk/islandsea-smoke-21045868
```

Ten wzorzec jest prawidłowy. Nie umieszczać katalogu roboczego Ray na współdzielonym NFS.

Job `21045867` zakończył się `FAILED 2:0`, ponieważ SLURM wykonał kopię skryptu z katalogu spool i nie znalazł względnego `smoke.py`. Zostało to naprawione przez użycie `SLURM_SUBMIT_DIR`.

## 7. Model zasobów aktualnego kodu

Obecny kod rezerwuje:

- `N` aktorów `Island`, po 1 CPU;
- `N` aktorów `Computation`, po 1 CPU;
- 1 aktora `SignalActor`, 1 CPU.

Potrzebne zasoby Ray:

```text
required_ray_cpus = 2*N + 1
```

Wrapper `run_ares.sh` wyłącza dodatkowo 1 CPU na head node z puli Ray dla procesu sterującego. Przy pełnych węzłach po 48 CPU:

| Wyspy | CPU wymagane przez Ray | Alokacja | CPU widziane przez Ray | Naliczane CPU |
|---:|---:|---:|---:|---:|
| 150 | 301 | 7 × 48 | 335 | 336 |
| 180 | 361 | 8 × 48 | 383 | 384 |
| 200 | 401 | 9 × 48 | 431 | 432 |

Możliwa późniejsza optymalizacja po pilocie to częściowe węzły: odpowiednio `7×44`, `8×46`, `9×45`. Dają one 307, 367 i 404 CPU Ray, czyli nadal spełniają warunek. Nie mieszać jednak rozmiarów alokacji w porównywanych wariantach — harmonogram aktorów wpływa na badane opóźnienia. Najpierw należy zwalidować prosty wariant z 48 CPU/węzeł.

Nie wolno „optymalizować” adnotacji `num_cpus` w aktorach wyłącznie po to, aby obniżyć koszt. Zmienia to harmonogram wykonania i może zmienić semantykę eksperymentu.

Launcher wykonuje teraz pełny dry-run i sprawdzenie powyższego wzoru przed uruchomieniem trwałych procesów Ray. Dla 200 wysp przydział mniejszy niż 402 fizyczne CPU jest odrzucany od razu. Dedykowany `run_ares_200.sh` przydziela 432 CPU, reklamuje Rayowi 431 i pozostawia 30 CPU zapasu ponad 401 wymaganych. Nie zmienia to ograniczeń topologii: przy N=200 aktualnie przechodzą `complete` i `ring`.

## 8. Skala kampanii i CPU-hours

Planowana macierz:

```text
5 topologii × 3 strategie × 40 benchmarków × 3 powtórzenia = 1800 uruchomień
```

Przy 8000 ewaluacji na wyspę całkowita liczba ewaluacji wyniesie:

| Wyspy | Ewaluacje/run | Ewaluacje/1800 runów |
|---:|---:|---:|
| 150 | 1 200 000 | 2,16 mld |
| 180 | 1 440 000 | 2,592 mld |
| 200 | 1 600 000 | 2,88 mld |

Koszt pełnej kampanii przy pełnych węzłach zależy liniowo od wall time pojedynczego joba:

```text
CPUh_total = liczba_runów × AllocCPUS × średni_walltime_w_godzinach
```

| Średni wall time/run | 150 wysp, 336 CPU | 180 wysp, 384 CPU | 200 wysp, 432 CPU |
|---:|---:|---:|---:|
| 5 min | 50 400 CPUh | 57 600 CPUh | 64 800 CPUh |
| 10 min | 100 800 CPUh | 115 200 CPUh | 129 600 CPUh |
| 15 min | 151 200 CPUh | 172 800 CPUh | 194 400 CPUh |
| 30 min | 302 400 CPUh | 345 600 CPUh | 388 800 CPUh |
| 60 min | 604 800 CPUh | 691 200 CPUh | 777 600 CPUh |

Do planowania grantu należy dodać co najmniej 20% na walidacje, nieudane joby, rozrzut czasu i narzut startu Ray. Na przykład 180 wysp i 10 min/run daje `115200 CPUh`, a z 20% buforem `138240 CPUh`.

Wartości te nie są prognozą czasu. Różne benchmarki i strategie mogą mieć bardzo różny koszt. Prognozę wyznaczamy dopiero z kilku pełnych, reprezentatywnych pilotów:

```bash
python smoke_run/slurm_job_cost.py JOB_ID_1 JOB_ID_2 JOB_ID_3 \
  --planned-runs 1800 \
  --overhead-percent 20 \
  --json-output "$SCRATCH/islandsEA/results/diagnostics/job_cost_pilots.json"
```

## 9. Krytyczny problem porównywalności topologii

Aktualnie dostępne topologie nie mają jednej wspólnej liczby wysp:

| Topologia CLI | Obsługiwane N |
|---|---|
| `complete` | dowolne dodatnie N |
| `ring` | praktycznie N≥3; istniejący graf zawiera także self-neighbour |
| `torus` | N≥24 i podzielne przez 12; w zakresie 150–200: 156, 168, 180, 192 |
| `er1`–`er4` | dokładnie 150 |
| `ws3`, `ws4` | dokładnie 144 |

Wniosek: nie da się obecnie przeprowadzić czystego porównania `complete/ring/torus/ER/WS` dla tego samego N w zakresie 150–200. Dostępne opcje metodologiczne:

1. badać `complete/ring/torus` przy N=180, ale wtedy są tylko trzy rodziny topologii;
2. użyć istniejących ER150 i WS144, akceptując konfuzję „topologia + liczba wysp”;
3. uzgodnić i wygenerować stałe grafy ER/WS dla wspólnego N, zapisać je w repo i hashować w manifestach.

Opcja 3 jest zmianą aparatury badawczej i wymaga jawnej decyzji przed kampanią. Nie regenerować grafów automatycznie podczas joba.

Trzeba także zamrozić, co dokładnie oznaczają „3 strategie”: trzy strategie selekcji migrantów, trzy strategie akceptacji czy trzy pary selekcja–akceptacja. Launcher obsługuje oba osobne parametry.

## 10. Wyniki, quota i liczba plików

### Aktualna quota katalogu domowego

```text
zajęte: około 4.95 GB
limit:  10 GB
pliki:  67 946
limit:  100 000
```

Pozostało około 5 GB i 32 tys. inode’ów. Repo zajmuje 35 MB, venv 893 MB, a `~/artifacts` podczas diagnostyki tylko 48 KB.

### Dostępny storage i aktualne miejsce zapisu

```text
HOME:    /net/people/plgrid/plgblaszczykk
         10 GB, zajęte ~4.9 GB; 100 000 plików, zajęte ~67 747
SCRATCH: /net/afscra/people/plgblaszczykk
         hard limit ~12 TiB; zajęte ~3 GB; 1 000 000 plików, zajęte ~78 252
```

`$PLG_GROUPS_STORAGE=/net/pr2/projects/plgrid`; `$PLG_GROUPS_SCRATCH` jest pusty.
Scratch jest przestrzenią roboczą, nie trwałym backupem.

### Gdzie zapisuje zaktualizowany launcher

Surowe wyniki:

```text
$SCRATCH/islandsEA/results/runs/<data>/<benchmark><dimension>/<run>/
```

Kopia manifestu i topologii/audit:

```text
$SCRATCH/islandsEA/results/audit/<run>/
```

Finalizowane piloty i archiwa są w `$SCRATCH/islandsEA/results/pilot_runs/`, logi
SLURM w `$SCRATCH/islandsEA/logs/slurm/`, a logi Ray zbierane po błędzie w
`$SCRATCH/islandsEA/logs/ray_failures/`. `checkpoints/` i `tmp/` są przygotowanymi
rootami dla kolejnych mechanizmów. Ray i cache Matplotlib celowo używają
node-local `/tmp`, nie współdzielonego scratcha. Repo i venv pozostają w HOME.

Każdy run ma agregowalny `run_metadata.json`: wszystkie parametry benchmarku,
GA, migracji i topologii, repeat/seed, `run_id`, `experiment_key`, hash pełnej
konfiguracji i grafu, commit/kod/wersje, zasoby i identyfikatory SLURM oraz
rozstrzygnięte ścieżki outputów. Finalizer odrzuca brak lub niespójność tego pliku.

Lokalny dwuwyspowy pilot utworzył 26 plików w katalogu runa. Obecny kontrakt generuje około 9 plików per wyspa plus pliki wspólne, zatem dla 180 wysp należy oczekiwać około **1628–1629 plików na run**. Dla 1800 runów byłoby to około **2,93 miliona surowych plików**, bez uwzględnienia logów SLURM. Limit 100 tys. plików wyklucza przechowywanie całej kampanii w formie rozpakowanej.

Wymagany przed produkcją pipeline:

1. ustalić współdzielony filesystem o odpowiedniej pojemności albo pracować małymi falami;
2. po każdym poprawnie zakończonym runie zachować cały katalog jako jedno archiwum z manifestem;
3. pobrać archiwum do lokalnego `artifacts` i zweryfikować checksum;
4. dopiero po weryfikacji usuwać surowy katalog/archiwum z Aresa;
5. mierzyć `du -sh` i liczbę plików po pełnym pilocie;
6. mocno ograniczyć równoległość, dopóki archiwizacja nie działa.

Limit HOME nie ma już ograniczać uruchomień. Nadal należy monitorować inode'y
SCRATCH (limit 1 mln), archiwizować ukończone fale i pobierać ważne wyniki na
laptop. `/tmp` węzła nadaje się na dane Ray, ale nie jako bezpośredni wspólny
katalog wyników dla aktorów działających na wielu węzłach.

Rozmiaru danych nie wolno ekstrapolować ze smoke testu. Pełny pilot 8000 ewaluacji ma zmierzyć zarówno bajty, jak i inode’y.

## 11. Zalecana kolejność następnych działań

Wszystkie polecenia uruchamiać z root repozytorium:

```bash
cd ~/islandsEA_student_fork
git pull --ff-only
git status --short --branch
```

### Krok A — walidacja 40 benchmarków na compute node

```bash
bash hpc_benchmarks/submit_validation.sh
```

Warunek przejścia: job `COMPLETED 0:0`, plik `$SCRATCH/islandsEA/results/validation/validation-<JOBID>.json`, `17` testów, zero błędów/pominięć, `success: true`.

### Krok B — dwa małe testy prawdziwej komunikacji Ray

```bash
bash hpc_benchmarks/submit_ares.sh \
  --problem b03_nk_k4 --dimension 60 --islands 2 --evaluations 128 \
  --topology complete --strategy maxDistance --acceptance plain

bash hpc_benchmarks/submit_ares.sh \
  --problem r29_composition7 --dimension 200 --islands 2 --evaluations 128 \
  --topology complete --strategy best --acceptance plain
```

Warunek przejścia: `COMPLETED 0:0`, linia `BENCHMARK_RUN_OK=...`, komplet manifestów oraz pliki dla obu wysp.

### Krok B2 — canary pełnej architektury 200 wysp

Po dwóch małych testach uruchomić dokładnie jeden job tworzący wszystkie 401 aktorów, ale z małym budżetem ewaluacji:

```bash
sbatch hpc_benchmarks/run_ares_200.sh \
  --problem r29_composition7 --dimension 200 --evaluations 128 \
  --population 16 --offspring 4 --migrants 5 --interval 5 \
  --topology complete --strategy best --acceptance plain \
  --repeat 1 --seed 20260912
```

Warunek przejścia: `COMPLETED 0:0`, `BENCHMARK_RUN_OK`, dziewięć linii `MPL_CACHE_READY`, linia `RESOURCE_PLAN` z `available_ray_cpus=431 required_ray_cpus=401` oraz komplet wyników dla 200 wysp. Domyślny walltime 30 minut ogranicza koszt nieudanego canary do maksymalnie 216 CPUh.

### Krok C — decyzje metodologiczne

Przed pełnym pilotem zamrozić:

- wspólne N i pięć topologii;
- trzy warianty strategii wraz z acceptance;
- wymiary poszczególnych 40 benchmarków;
- bazowy seed i mapowanie repeatów;
- identyczną alokację zasobów dla porównywanych runów;
- miejsce składowania i format archiwum.

### Krok D — pełnowymiarowe, reprezentatywne piloty

Przykład poprawnego zasobowo pilota dla 180 wysp i torusa:

```bash
sbatch -A plglscclass26-cpu -p plgrid \
  --nodes=8 --ntasks-per-node=1 --cpus-per-task=48 \
  --mem-per-cpu=2G --time=01:00:00 \
  hpc_benchmarks/run_ares.sh \
  --problem r29_composition7 --dimension 200 --islands 180 \
  --evaluations 8000 --population 16 --offspring 4 \
  --migrants 5 --interval 5 --topology torus \
  --strategy best --acceptance plain --repeat 1 --seed 20260912
```

`01:00:00` jest limitem startowym do pilota, nie zmierzonym czasem. Pilotów powinno być kilka: co najmniej wolniejszy i szybszy problem ciągły, problem binarny oraz warianty strategii/topologii potencjalnie skrajne czasowo.

Po każdym pilocie zapisać:

```bash
sacct -j JOB_ID -P \
  --format=JobIDRaw,JobName,State,ExitCode,ElapsedRaw,AllocCPUS,CPUTimeRAW,TotalCPU,MaxRSS,ReqMem,NodeList

du -sh PATH_Z_BENCHMARK_RUN_OK
find PATH_Z_BENCHMARK_RUN_OK -type f | wc -l
```

Następnie policzyć koszt z kilku jobów przez `smoke_run/slurm_job_cost.py`.

### Krok E — dopiero potem kampania

- wygenerować jawny manifest 1800 konfiguracji;
- używać job arrays/fal z ograniczoną równoległością;
- nie wysyłać wszystkich 1800 elementów jednocześnie z uwagi na `MaxSubmitJobs=1000`, fairshare i quota;
- obsłużyć retry tylko dla jawnie nieudanych runów, zachowując te same parametry i seed;
- monitorować CPUh, rozmiar wyników, liczbę plików i odsetek awarii po każdej fali.

## 12. Polecenia diagnostyczne

Pełna diagnostyka środowiska i wskazanych jobów:

```bash
cd ~/islandsEA_student_fork/smoke_run
bash collect_ares_info.sh JOB_ID_1 JOB_ID_2
```

Raport trafia do:

```text
$SCRATCH/islandsEA/results/diagnostics/ares_diagnostics_<timestamp>.txt
```

Szybka kontrola joba:

```bash
sacct -j JOB_ID --format=JobID,JobName,Partition,Account,State,ExitCode,Elapsed,AllocCPUS,CPUTime,MaxRSS,NodeList
```

## 13. Reguły bezpieczeństwa eksperymentalnego

- Nie wykonywać benchmarków lokalnie na laptopie.
- Nie używać legacy skryptów `run150*.sh` jako produkcyjnych: zawierają stare granty, błędne kontrakty argumentów lub odwołania do brakującego `start_bm.py`.
- Używać `hpc_benchmarks/run_ares.sh`, profilu `hpc_benchmarks/run_ares_200.sh` i `hpc_benchmarks/validate_ares.sh`.
- Opcje SLURM (`-A`, `-p`, `--nodes`, `--time`, CPU, RAM) podawać **przed** nazwą skryptu; opcje eksperymentu podawać po nazwie skryptu.
- Submit wykonywać z root repo, nie z `hpc_benchmarks/` ani `smoke_run/`, chyba że jawnie ustawiono `ISLANDS_PROJECT_DIR`.
- Nie zmieniać semantyki migracji, kolejności odbioru, znaku delay ani rezerwacji aktorów bez decyzji badawczej.
- `--interval` oznacza różnicę licznika ewaluacji, nie pokolenia.
- `--repeat` uruchamia jedno powtórzenie. Seed wyspy to `seed + (repeat-1)*1000000 + island_id`.
- Asynchroniczny Ray nie gwarantuje identycznego przebiegu nawet dla tego samego seeda.
- D=200 dla funkcji CEC jest rozszerzeniem IslandsEA, nie oficjalną instancją CEC2014.
- Zachowywać surowe logi migrantów oraz `benchmark_manifest.json`, `experiment_manifest.json`, `topology.json` i `iterations_per_second.json`.

## 14. Otwarte kwestie / blokery przed produkcją

1. Jaki jest dokładny pozostały budżet CPU-hours grantu `plglscclass26-cpu`?
2. Jakie dokładnie pięć topologii i wspólna liczba wysp mają wejść do porównania?
3. Jakie dokładnie trzy strategie/pary strategii badamy?
4. Jaki filesystem lub pipeline archiwizacji pomieści wyniki?
5. Jaki jest wall time, `MaxRSS`, rozmiar i liczba plików pełnego pilota?
6. Jaka zgodna wersja `wheel` zamknie `pip check` bez zmiany przypiętego runtime?
7. Jaka bezpieczna równoległość fal nie przeciąży quota, metadanych NFS i fairshare?

Do czasu odpowiedzi na punkty 1–5 można bezpiecznie wykonywać walidację, dwa małe testy Ray i ograniczoną serię pilotów. Nie ma jeszcze podstaw do wysłania pełnych 1800 runów.
