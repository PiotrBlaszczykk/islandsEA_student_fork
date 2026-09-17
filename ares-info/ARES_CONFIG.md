> Aktualizacja 2026-09-17: badanie używa 144 wysp we wszystkich topologiach.
> ER4 został odblokowany zgodnie z odpowiedzią prowadzącej: igraph G(n,p),
> n=144, p=0.0347, undirected; pętle tylko dla izolowanych węzłów.
> Zamrożony graf ma 365 krawędzi, składową 144 i zero pętli; seed 20260917.
> Szczegóły: [generacja ER4](../hpc_benchmarks/ER4_GENERATION.md).
> Poniższa treść jest historyczną migawką debugowania. Historyczne pomiary i stare załączniki pozostają archiwalne; D=200 jest wymiarem.

# IslandsEA na Aresie — konfiguracja, stan i bezpieczne uruchamianie

Ostatnia aktualizacja: **2026-09-14**  
Klaster: **Ares / Cyfronet / PLGrid**  
Użytkownik: `plgblaszczykk`  
Branch roboczy dla Aresa: `summer_benchmarks`  
Zweryfikowany lokalny commit: `ca5cd17b28c62676bb86575ffea2e12e7aa592b2` (`Add unattended gated pilot launcher`)

Ten dokument jest technicznym handoffem dla kolejnych sesji pracujących nad
uruchomieniami IslandsEA na Aresie. Opisuje środowisko, model zasobów, storage,
konfigurację naukową, pipeline pilota, format danych, koszty i znane awarie.
Nie należy interpretować go jako potwierdzenia, że pełny pilot został wykonany.

## 1. Stan w jednym miejscu

| Element | Stan |
|---|---|
| SLURM + Python + venv + Ray na jednym węźle | **potwierdzone** przez smoke `21045868` |
| 40 nazwanych benchmarków i dry-run konfiguracji | **zaimplementowane**; lokalne testy przechodziły |
| Multi-node launcher Ray dla 144 wysp | head i readiness potwierdzone w `21077531`; poprawiany jest podział CPU/pamięci head-driver |
| Storage wyników i logów pod `$SCRATCH/islandsEA` | **zaimplementowany** |
| Pełna telemetria `research-v1-full-buffered` | **zaimplementowana**, wymaga walidacji na pełnym canary/pilocie |
| Pipeline canary → gate → 3 powtórzenia → finalizer | **zaimplementowany**; pełne powtórzenia pozostają zablokowane do poprawnego canary |
| Canary 144 wysp | `21077531` zaliczył head readiness; driver został odrzucony, bo head step zajął pamięć wszystkich 48 CPU |
| Pełny pilot: torus 12×12, 144 wyspy, 3 powtórzenia | **nie został wysłany** |
| Kampania 1800 runów | **niegotowa**; potrzebuje poprawnego pilota i estymacji |

Naprawa `/var/spool/slurmd` jest potwierdzona przez canary `21076864`: batch
odczytał checkout przez absolutne `ISLANDS_PROJECT_DIR`, zweryfikował plan 144
wysp, przygotował cache Matplotlib na siedmiu węzłach i dotarł do startu head
node. Click przywrócono z 8.5.0 do zatwierdzonego 8.2.1. Canary `21077082`
potwierdził następnie zdrowy GCS i raylet, ale pomocniczy readiness check przez
osobny krok `srun` nie dotarł do GCS. Canary `21077531` zaliczył poprawiony
readiness, po czym ujawnił błąd podziału zasobów: head step rezerwował wszystkie
48 CPU i ich pamięć, pozostawiając Ray 47 CPU, ale nie zostawiając SLURM-owi
pamięci na driver. Bieżąca poprawka rezerwuje dla head 47 CPU, a dla drivera
pozostały 1 CPU i 2 GB jako rozłączne kroki `--exact`.

## 2. Źródła prawdy i poziom pewności

Źródła lokalne:

- `main_codebase/islandsEA_student_fork/AGENTS.md` — kontrakt projektu, aktywna
  ścieżka wykonania i semantyka eksperymentu;
- `main_codebase/ARES_INFO.md` — diagnostyka środowiska i wcześniejszy plan;
- `main_codebase/ares_diagnostics.txt` — migawka Aresa z 2026-09-12;
- `main_codebase/job_cost_smoke.json` — rozliczenie smoke `21045868`;
- `main_codebase/islandsEA_student_fork/hpc_benchmarks/` — launcher Ray/SLURM,
  storage i walidacja;
- `main_codebase/islandsEA_student_fork/pilot_run/` — zamrożona specyfikacja,
  pipeline, walidator, finalizer i downloader;
- logi `sacct` i stderr jobów `21059904` oraz `21059905` przekazane przez
  operatora 2026-09-14;
- `sacct`, stdout i stderr canary `21076864` przekazane przez operatora
  2026-09-16.

Wartości dotyczące partycji, quota, fairshare i kolejki są migawkami. Przed
każdym kosztownym uruchomieniem należy sprawdzić je ponownie. Konfigurację
eksperymentu odczytujemy z `pilot_run/pilot_spec.json`, a nie z pamięci ani ze
starego PDF. Fakty o wykonaniu potwierdzamy przez `sacct` i artefakty, nigdy
samym `squeue`.

## 3. Rozdzielenie Aresa i Atheny

Ares jest docelową ścieżką **CPU/multi-node** aktualnej implementacji. Athena
jest osobnym portem GPU i ma osobny branch `summer_benchmarks_athena` oraz
`ATHENA_CONFIG.md`.

Na Aresie:

- branch: `summer_benchmarks`;
- konto CPU: `plglscclass26-cpu`;
- partycja produkcyjna: `plgrid`;
- nie rezerwujemy GPU;
- jedna wyspa i jedna jednostka obliczeniowa są obecnie osobnymi aktorami Ray;
- obliczenia benchmarkowe odbywają się wyłącznie w alokacji SLURM.

Nie kopiować do Aresa założeń GPU z Atheny i nie przenosić zmian między
branchami bez jawnego przeglądu. Kod na laptopie jest źródłem zmian; Ares służy
do `git pull --ff-only`, uruchamiania i przechowywania roboczych artefaktów.

## 4. Stałe ścieżki

### Ares

```text
HOME:       /net/people/plgrid/plgblaszczykk
repo:       /net/people/plgrid/plgblaszczykk/islandsEA_student_fork
venv:       /net/people/plgrid/plgblaszczykk/venvs/islands-ray
SCRATCH:    /net/afscra/people/plgblaszczykk
root danych:$SCRATCH/islandsEA
```

Domyślny kontrakt `hpc_benchmarks/ares_storage.sh`:

```text
$SCRATCH/islandsEA/
├── results/
│   ├── runs/                 # surowe wyniki algorytmu
│   ├── audit/                # małe manifesty/audyt
│   └── pilot_runs/           # canary, finalizacja i archiwa pilota
├── logs/
│   ├── slurm/                # stdout/stderr jobów
│   └── ray_failures/         # zebrane logi Ray po awarii
├── checkpoints/
└── tmp/
```

Rozstrzygnięte zmienne:

```text
ISLANDS_STORAGE_ROOT
ISLANDS_RESULTS_ROOT
ISLANDS_LOG_ROOT
ISLANDS_CHECKPOINT_ROOT
ISLANDS_TMP_ROOT
ISLANDS_RUN_OUTPUT_ROOT
ISLANDS_AUDIT_ROOT
ISLANDS_ARTIFACT_ROOT
ISLANDS_SLURM_LOG_DIR
ISLANDS_RAY_FAILURE_ROOT
```

Każdą można nadpisać, ale standardem dla Aresa jest `$SCRATCH/islandsEA`.
Fallback do `$HOME/islandsEA` istnieje dla ręcznych testów i wypisuje
ostrzeżenie. Główny launcher pilota blokuje submit, jeżeli `$SCRATCH` nie jest
ustawiony albo storage root nie leży pod nim.

### Laptop

```text
repo:    C:\Users\piotr\UMISI\IslandsEA_summer\main_codebase\islandsEA_student_fork
wyniki:  C:\Users\piotr\UMISI\IslandsEA_summer\artifacts
handoff: C:\Users\piotr\UMISI\IslandsEA_summer\main_codebase\ARES_CONFIG.md
```

Scratch nie jest backupem. Finalne wyniki należy pobrać na laptop, zweryfikować
checksumy i dopiero wtedy ewentualnie czyścić na klastrze.

## 5. System, węzły i SLURM

| Parametr | Potwierdzona wartość |
|---|---|
| Login | `login01.ares.cyfronet.pl` |
| System | Linux, kernel `4.18.0-553.144.1.el8_10.x86_64` |
| SLURM | `23.11.6` |
| Selekcja zasobów | `select/cons_tres`, `CR_CPU_MEMORY` |
| Standardowy compute node | 48 fizycznych rdzeni, `ThreadsPerCore=1` |
| RAM standardowego węzła | około `184800 MB` |
| Przykładowa rodzina CPU | Intel Xeon Cascade Lake |
| Maksymalny rozmiar array klastra | `20001` |
| Limit submitów asocjacji | `MaxSubmitJobs=1000` |

Login node zgłaszał 12 CPU; ta liczba nie opisuje compute nodes i nie może być
używana do planowania. Nie uruchamiamy benchmarków na login node.

Konto i partycje:

| Pole | Wartość / użycie |
|---|---|
| konto | `plglscclass26-cpu` |
| QOS | `normal` |
| `plgrid` | produkcja, maks. 3 dni |
| `plgrid-now` | maks. 12 h; używać tylko świadomie |
| `plgrid-testing` | maks. 1 h i 2 węzły; gate/finalizer/małe testy |
| `plgrid-long`, `plgrid-bigmem` | dostęp niepotwierdzony; nie planować |

Domyślny czas `plgrid` to tylko 15 minut. Każdy job ma jawnie określać
`--time`. `plgrid` raportował `DefMemPerCPU=3850 MB`, a bieżące launchery proszą
o `--mem-per-cpu=2G`. Wagi billingowe (`cpu=1`, `mem=0.265G`) oznaczają, że bez
pomiaru nie należy nadmiernie zwiększać pamięci.

Fairshare `0.090663` z raportu był tylko chwilową migawką. Później konto było
silnie zajęte przez wielodniowe joby innego użytkownika, co tłumaczyło długie
`PENDING (Priority)`. Czas oczekiwania nie zużywa CPU-hours i nie jest objęty
`TIME_LIMIT`; limit biegnie dopiero w stanie `RUNNING`.

## 6. Python i venv

Aktywacja na Aresie:

```bash
module load python/3.10.4-gcccore-11.3.0
source "$HOME/venvs/islands-ray/bin/activate"
```

Potwierdzone wersje:

| Pakiet | Wersja |
|---|---:|
| Python | `3.10.4` |
| Ray | `2.9.3` |
| Click | `8.2.1` po cofnięciu z niezgodnego `8.5.0` |
| jMetalPy | `1.5.5` |
| NumPy | `1.21.4` |
| SciPy | `1.7.3` |
| scikit-learn | `1.1.3` |
| pandas | `1.3.4` |
| matplotlib | `3.5.0` |
| setuptools | `80.10.2` |
| wheel | `0.48.0` |
| packaging | `21.3` |

`setuptools<81` jest celowe: Ray 2.9.x importuje jeszcze `pkg_resources`.
Ostrzeżenie o deprecjacji nie było błędem smoke'a. `pip check` zgłasza jednak:

```text
wheel 0.48.0 has requirement packaging>=24.0, but packaging 21.3 is installed
```

Nie podnosić ślepo `packaging`, bo projekt przypina `21.3`. Przed produkcją
należy dobrać zgodną wersję `wheel`, wykonać `pip check`, testy, mały Ray run i
zapisać `pip freeze`. Sam konflikt nie unieważnia działającego smoke'a.

## 7. Potwierdzony smoke i lekcja ze ścieżek SLURM

Smoke `21045868`:

| Pole | Wartość |
|---|---|
| stan | `COMPLETED`, `ExitCode=0:0` |
| węzeł | `ac0640` |
| zasoby | 2 CPU, 4 GB |
| czas | 7 s |
| koszt | 14 CPU-s = `0.0038889 CPUh` |
| Ray | zdalny task wykonał się i zwrócił wynik |
| marker | `SMOKE_TEST_OK` |

Ray używał node-local:

```text
/tmp/plgblaszczykk/islandsea-smoke-21045868
```

Poprzedni smoke `21045867` padł, bo po submit skrypt szukał `smoke.py` w
`/var/spool/slurmd/job21045867/`. Naprawa polegała na oparciu ścieżki na
`SLURM_SUBMIT_DIR`/jawnie przekazanym katalogu projektu. Obecna awaria pilota
jest powtórzeniem tej samej klasy błędu, tylko w innym wrapperze.

Projekcja `8.4 CPUh` z siedmiosekundowego smoke'a dla 1800 uruchomień jest
arytmetyką smoke'a, a **nie** estymacją kampanii.

## 8. Aktywna architektura IslandsEA na CPU

Dla `N` wysp kod tworzy:

- `N` aktorów `Island`, każdy z `num_cpus=1`;
- `N` aktorów `Computation`, każdy z `num_cpus=1`;
- 1 aktora `SignalActor`, `num_cpus=1`;
- proces drivera, dla którego launcher pozostawia 1 fizyczny CPU poza pulą Ray.

Wzory:

```text
required_ray_cpus   = 2*N + 1
required_slurm_cpus = 2*N + 2
```

| Wyspy | Wymagane CPU Ray | Prosta alokacja | CPU reklamowane Ray | Naliczane CPU |
|---:|---:|---:|---:|---:|
| 150 | 301 | 7 × 48 | 335 | 336 |
| 180 | 361 | 8 × 48 | 383 | 384 |
| 200 | 401 | 9 × 48 | 431 | 432 |

Dla pilota 200 wysp rezerwujemy 9 pełnych węzłów. Head reklamuje 47 CPU, każdy
z ośmiu workerów 48 CPU, razem 431; 401 zajmują aktorzy. Zapas chroni przed
deadlockiem zasobów, a dodatkowy CPU na head obsługuje driver.

Nie zmniejszać `num_cpus` aktorów i nie oversubskrybować CPU tylko dla
oszczędności. Harmonogram jest częścią badanego systemu i wpływa na opóźnienia
migracji. Launcher ustawia `OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`,
`MKL_NUM_THREADS` i `NUMEXPR_NUM_THREADS` na 1, aby każdy aktor nie tworzył
dodatkowych wątków BLAS.

## 9. Jak działa launcher multi-node Ray

Główny wrapper to `hpc_benchmarks/run_ares.sh`:

1. wymaga aktywnej alokacji SLURM;
2. rozwiązuje repo z `ISLANDS_PROJECT_DIR`, awaryjnie z `SLURM_SUBMIT_DIR`;
3. konfiguruje storage i venv;
4. wykonuje dry-run `run_benchmark.py` i sprawdza zasoby przed startem Ray;
5. pobiera listę węzłów z `SLURM_JOB_NODELIST`;
6. rozgrzewa osobny cache Matplotlib na każdym węźle;
7. uruchamia Ray head na pierwszym węźle i worker na każdym kolejnym;
8. czeka na gotowość head;
9. uruchamia head step na 47 CPU, a driver jako rozłączny `srun --exact` na
   pozostałym 1 CPU i 2 GB;
10. po sukcesie sprząta Ray; po błędzie próbuje spakować per-node logi do
   `$SCRATCH/islandsEA/logs/ray_failures/`.

Port Ray jest wyznaczany z job ID:

```text
20000 + SLURM_JOB_ID % 20000
```

Ray, `TMPDIR`, cache XDG i Matplotlib używają lokalnego `/tmp`, a nie NFS.
Aktualny wzorzec to `/tmp/$USER/islandsea-$SLURM_JOB_ID`. Należy pilnować limitu
107 bajtów dla socketów `AF_UNIX`; gdy pojawi się błąd długości socketu, użyć
krótkiego rootu typu `/tmp/r$SLURM_JOB_ID`. Nie przenosić sesji Ray na wspólny
scratch — każdy węzeł ma własny lokalny `/tmp`.

Historyczna awaria Ray zużyła około 30 tys. CPU-hours. Dlatego obowiązują:
krótki canary, twardy walltime, timeout startu aktorów, walidacja zasobów przed
Ray, brak automatycznych retry, zbieranie logów z każdego węzła i stop całego
joba przy niespodziewanym błędzie odbioru migrantów.

## 10. Zamrożona konfiguracja obecnego pilota

Źródło: `pilot_run/pilot_spec.json`, schema 2.

| Pole | Wartość |
|---|---:|
| nazwa | `torus200-r01-d200-best-plain` |
| benchmark | `r01_elliptic` |
| rodzina | ciągła |
| wymiar | 200 |
| wyspy | 200 |
| ewaluacje na wyspę | 8000 |
| populacja | 16 |
| offspring | 4 |
| liczba migrantów | 5 |
| interwał migracji | 5 |
| topologia | torus 10 × 20 |
| selekcja migrantów | `best` |
| akceptacja | `plain` |
| powtórzenia | 1, 2, 3 |
| seed bazowy | `20260912` |
| kroki na wyspę | 1996 |
| próg silnego delay | 10 kroków |
| horyzont przeżycia | 25 kroków |
| profil metryk | `research-v1-full-buffered` |

Interwał 5 oznacza różnicę licznika **ewaluacji** w istniejącej implementacji,
nie pięć generacji. `plain` jest baseline'em akceptacji i nie stosuje filtra
wieku/jakości. D=200 dla F1 jest rozszerzeniem projektu, a nie oficjalnym
wymiarem CEC2014; metadane mają to jawnie oznaczać.

Torus 10×20 jest jawną nową konstrukcją dla 200 wierzchołków. Historyczny kod
używał 12×(N/12). Dlatego spec ma status
`pending_torus_10x20_confirmation`, a launcher wymaga świadomej flagi
`--confirm-torus200-and-722-cpuh`. Flaga została użyta przy pierwszym submit,
ale nie jest dowodem naukowej akceptacji przez prowadzącego.

## 11. Zaprojektowany pipeline pilota

Docelowy przebieg:

```text
login: preflight + dry-run
          |
          v
canary: 200 wysp, 128 ewaluacji, 9×48 CPU, 10 min
          |
          v  afterany
gate: sprawdzenie sacct + pełnego kontraktu danych
          |
          v  tylko po sukcesie
array 1-3%3: trzy pełne powtórzenia, po 9×48 CPU, 30 min
          |
          v  afterany
finalizer: walidacja, analiza, sacct, archiwa i checksumy
```

`afterany` jest celowe: gate/finalizer uruchamiają się również po błędzie, aby
go zapisać i zweryfikować. Nie oznacza to, że droga seria wystartuje po
nieudanym canary — `submit_pilot.sh verify-canary` ma ją zablokować.

Sufity kosztu:

| Etap | Alokacja i limit | Maksymalny koszt |
|---|---|---:|
| canary | 432 CPU × 10 min | 72 CPUh |
| pełne 3 powtórzenia | 3 × 432 CPU × 30 min | 648 CPUh |
| finalizer | 1 CPU × 1 h | 1 CPUh |
| gate | 1 CPU × 30 min | 0.5 CPUh |
| razem | — | 721.5 CPUh, zaokrąglone do 722 |

Przy równoległości 3 szczytowa alokacja pełnego pilota to 27 węzłów i 1296
CPU. `PILOT_MAX_PARALLEL=1` lub `2` zmniejsza szczytową równoległość, nie
zmienia konfiguracji powtórzeń ani sumarycznego sufitu CPUh.

## 12. Forensics pierwszego submitu pilota

Uruchomiono z czystego `summer_benchmarks`, commit `ca5cd17`:

```bash
bash pilot_run/launch_pilot.sh --confirm-torus200-and-722-cpuh
```

Powstały:

```text
canary: 21059904
gate:   21059905
```

Rozliczenie:

```text
21059904 island-pilot-canary FAILED 1:0 00:00:01 AllocCPUS=432 CPUTimeRAW=432
21059905 island-pilot-gate   FAILED 1:0 00:00:02 AllocCPUS=1   CPUTimeRAW=2
```

Dokładny błąd canary:

```text
/var/spool/slurmd/job21059904/slurm_script: line 19:
/var/spool/slurmd/hpc_benchmarks/ares_storage.sh: No such file or directory
```

Dokładny błąd gate:

```text
/var/spool/slurmd/job21059905/slurm_script: line 25:
/var/spool/slurmd/hpc_benchmarks/ares_storage.sh: No such file or directory
```

Przyczyna jest jednoznaczna: batch script liczył `SCRIPT_DIR` z położenia
skopiowanego pliku SLURM. Nie była to awaria Ray, benchmarku, torusa, venva ani
storage. Ray i właściwy compute nie zdążyły wystartować.

Gate poprawnie nie wysłał array. W
`$SCRATCH/islandsEA/results/pilot_runs/pilot_canaries/21059904/` pozostał tylko
`pipeline_submission.json` ze statusem `canary_and_gate_submitted`; brak
`array_job_id` i `finalizer_job_id`. Pełne trzy powtórzenia **nie istnieją**.

Koszt awarii to około 432 CPU-sekund = `0.12 CPUh` dla canary plus pomijalny
gate. Nie należy szukać wyników benchmarku ani traktować tego jako naukowego
powtórzenia.

### Canary 144 po naprawie spool: `21076864`

Canary uruchomiono z commita `e96b53e` i wyłącznie jako pojedynczy job, bez gate
i pełnych powtórzeń. Preflight na login node potwierdził 144 wyspy, torus 12×12,
289 CPU Ray i 290 minimalnych CPU SLURM. Rozliczenie:

```text
21076864 island-pilot-canary FAILED 1:0 00:00:07 AllocCPUS=336 CPUTimeRAW=2352
```

Job poprawnie użył `$SCRATCH/islandsEA`, rozgrzał cache Matplotlib na wszystkich
siedmiu węzłach i doszedł do `Starting HEAD`. Następnie samo wejście do CLI Ray
zakończyło się podczas importu:

```text
ValueError: <object object at ...> is not a valid Sentinel
Ray head exited during startup
```

To znana niezgodność CLI Ray z Click 8.3 i nowszym. Nie uruchomiono benchmarku, nie ma
`BENCHMARK_RUN_OK` ani artefaktów naukowych. Koszt alokacji wyniósł
2352 CPU-sekund, czyli około 0.65 CPUh. Przed następnym canary należy przypiąć
`click==8.2.1`, potwierdzić `ray --version` i pozostawić pełny pilot zablokowany.

### Canary 144 po naprawie Click: `21077082`

Canary uruchomiono z commita `14de749`. Ray 2.9.3 i Click 8.2.1 przeszły
preflight. Rozliczenie:

```text
21077082 island-pilot-canary FAILED 1:0 00:01:05 AllocCPUS=336 CPUTimeRAW=21840
```

Head Ray wystartował na `ac0111` pod `172.22.16.111:37082`. Logi awarii
potwierdzają, że GCS nasłuchiwał, raylet zarejestrował head node z 47 CPU, a
`gcs_server.err` i `raylet.err` były puste. Ostrzeżenie o niedostępnym agencie
metryk jawnie zaznacza, że nie wpływa na Ray. Mimo tego 30 prób readiness przez
dodatkowy `srun --overlap ... ray status` nie dotarło do GCS i po około minucie
launcher zakończył zdrowy proces head.

Nie uruchomiono workerów ani benchmarku; brak `BENCHMARK_RUN_OK` i artefaktów
naukowych. Koszt wyniósł 21840 CPU-sekund, czyli około 6.07 CPUh. Launcher ma
wykonywać readiness bezpośrednio z procesu batch na head node, zapisywać pełny
wynik ostatniego `ray status`. Przed trzema powtórzeniami nadal wymagany jest
nowy poprawny canary.

### Canary 144 po naprawie readiness: `21077531`

Canary uruchomiono z commita `da3de56`. Head Ray wystartował na `ac0252`, a
readiness przeszedł w drugiej próbie:

```text
RAY_HEAD_READY address=172.22.16.252:37531 attempt=2
```

Rozliczenie:

```text
21077531 island-pilot-canary FAILED 1:0 00:02:30 AllocCPUS=336 CPUTimeRAW=50400
```

Następny krok drivera został natychmiast odrzucony przez SLURM:

```text
srun: error: Unable to create step for job 21077531: Memory required by task is not available
```

Przy `--mem-per-cpu=2G` head step żądał 48 CPU i całej przypisanej im pamięci,
mimo że `ray start --num-cpus=47` pozostawiał logiczny CPU dla drivera. Błąd
drivera uruchomił cleanup i zabił head; późniejsze `Failed to connect to GCS`
na workerach były skutkiem tego zakończenia, a nie pierwotną awarią sieci.
Benchmark nie wystartował i nie powstały artefakty naukowe. Koszt wyniósł 50400
CPU-sekund, czyli 14 CPUh. Poprawka ustawia head step na 47 CPU oraz driver na
rozłączny krok `--exact` z pozostałym 1 CPU i 2 GB.

## 13. Naprawa błędu `/var/spool/slurmd`

Zasada ogólna:

> W skrypcie przekazanym do `sbatch` nie wolno wyznaczać położenia repo z
> `${BASH_SOURCE[0]}`. To wskazuje kopię w spool, nie oryginał w checkout.

Naprawę wdrożono w commicie `e96b53e`: wszystkie submittery eksportują
absolutne `ISLANDS_PROJECT_DIR`, a batch scripts wymagają tej zmiennej. Test
`pilot_run/test_spool_paths.py` uruchamia kopie wszystkich czterech etapów z
katalogu o kształcie `/var/spool/slurmd/job...`; canary `21076864` potwierdził
poprawkę na Aresie.

Submittery działające na login node mogą bezpiecznie wyznaczyć absolutne repo z
własnego `BASH_SOURCE`, a potem muszą przekazać je do joba:

```bash
--export="ALL,ISLANDS_PROJECT_DIR=${PROJECT_DIR},..."
```

Skrypty batch powinny wymagać tej wartości i wyprowadzać katalog helperów:

```bash
: "${ISLANDS_PROJECT_DIR:?Missing absolute repository path}"
PROJECT_DIR="$ISLANDS_PROJECT_DIR"
SCRIPT_DIR="$PROJECT_DIR/pilot_run"
```

Do poprawy i przeglądu:

- `pilot_run/submit_canary.sh` — eksport `ISLANDS_PROJECT_DIR`;
- `pilot_run/launch_pilot.sh` — eksport ścieżki do gate;
- `pilot_run/submit_pilot.sh` — eksport ścieżki do array i finalizera;
- `pilot_run/run_pilot_canary.sh` — nie używać spoolowego `BASH_SOURCE`;
- `pilot_run/continue_after_canary.sh` — to samo;
- `pilot_run/run_pilot_array.sh` — to samo;
- `pilot_run/finalize_pilot.sh` — to samo;
- `hpc_benchmarks/run_ares_200.sh` — wrapper również jest batch script i jest
  strukturalnie podatny;
- `smoke_run/run_smoke.sh` — sprawdzić regresję tej samej klasy.

`hpc_benchmarks/run_ares.sh` już preferuje `ISLANDS_PROJECT_DIR` i ma fallback
do `SLURM_SUBMIT_DIR`; to właściwy wzorzec. Fallback nadal trzeba walidować przez
sprawdzenie charakterystycznych plików repo.

Nie próbować rozwiązywać tego przez dynamiczne `$SCRATCH` w `#SBATCH --output`:
dyrektywy `#SBATCH` nie przechodzą zwykłej ekspansji shell. Dynamiczne logi na
scratch ustawia login-side wrapper przez opcje `sbatch --output=... --error=...`.

## 14. Walidacja naprawy przed drogim ponowieniem

Nie wystarczy naprawić tylko canary. Każdy batch stage musi przejść test
spool-like, ponieważ gate, array i finalizer mają tę samą klasę ryzyka.

Minimalny plan:

1. testy jednostkowe `pilot_run.test_pilot_tools`;
2. test/symulacja, w której kopia każdego batch scriptu znajduje się poza repo,
   a `ISLANDS_PROJECT_DIR` wskazuje checkout;
3. sprawdzenie, że submittery zawsze przekazują absolutną ścieżkę;
4. mała walidacja SLURM na `plgrid-testing` dla helpera nieuruchamiającego Ray;
5. dwa małe runy Ray na 2 wyspach;
6. dopiero potem ponowny canary 200 wysp;
7. gate ma utworzyć `canary_validation.json` i dopiero wtedy array/finalizer.

Warunki negatywne też muszą być sprawdzone: brak `ISLANDS_PROJECT_DIR`, zła
ścieżka, inny commit i brudny checkout mają kończyć job przed Ray z jasnym
komunikatem.

Do czasu nowego commita z tą naprawą polecenie
`pilot_run/launch_pilot.sh --confirm-torus200-and-722-cpuh` jest **zablokowane
operacyjnie**. Nie należy ponawiać go na `ca5cd17`.

## 15. Output i metadane każdego runa

Surowy run trafia domyślnie do:

```text
$SCRATCH/islandsEA/results/runs/<data>/<benchmark><dimension>/<run>/
```

Najważniejsze pliki wspólne obejmują:

```text
run_metadata.json
experiment_manifest.json
benchmark_manifest.json
param.json
topology.json
topology.png
iterations_per_second.json
metrics/data_contract.json
```

`run_metadata.json` jest kluczem do agregacji. Ma zawierać:

- stabilne `experiment_key`, unikalne `run_id`, repeat i seed;
- benchmark, rodzinę, wymiar i informację o rozszerzeniu wymiaru;
- liczbę wysp, ewaluacje, populację i offspring;
- liczbę migrantów, jednostkę interwału, selekcję i akceptację;
- nazwę topologii, parametry konstrukcji i hash adjacency;
- profil i wersję schematu metryk;
- commit Git, stan checkoutu, wersje Python/Ray/pakietów i hashe kodu;
- konto, partycję, job/array/task ID, hosty, żądane i przydzielone zasoby;
- rozstrzygnięte ścieżki storage, logów i artefaktów;
- czasy startu/końca i fazy runtime.

`param.json` sam nie jest wystarczającym źródłem reprodukowalności, ponieważ
historycznie odczytywał tekst operatora z innej ścieżki niż aktywny builder
HPC. Finalizator powinien porównywać wszystkie manifesty ze specyfikacją.

## 16. Profil metryk `research-v1-full-buffered`

Telemetria jest buforowana w pamięci wyspy podczas optymalizacji i kompresowana
po zakończeniu. Unikamy synchronicznego I/O na każdej migracji, bo zmieniłoby
ono badane opóźnienia.

Per wyspa:

```text
metrics/island_000..199/
├── migration_events.jsonl.gz
├── queue_fetches.jsonl.gz
├── fitness_history.jsonl.gz
├── final_solution.json
├── runtime.json
└── summary.json
```

Zdarzenia migracji używają wspólnego `(run_id, event_id)` i rejestrują etapy:

```text
send → enqueue → dequeue → process → filter → replacement → survival_horizon
```

Wymagane informacje obejmują źródło/cel, kroki i ewaluacje obu stron, fitness,
czas Unix, czas kolejki mierzony monotonicznie po stronie odbiorcy, głębokość
kolejki, decyzję, powód, przeżycie replacementu oraz przeżycie po 25 krokach.
Nierozstrzygnięty horyzont na końcu runa ma być `null`, nie `false`.

Kanoniczny delay:

```text
delay_steps = source_iteration_at_send - destination_step_at_receive
```

Znak jest informacją:

- `< 0` — migrant opóźniony;
- `> 0` — migrant przyspieszony;
- `= 0` — zsynchronizowany.

Nie zastępować signed delay wartością bezwzględną lub samym wall-clock latency.
Są to metryki uzupełniające.

Historia fitness ma punkt początkowy i każdy krok oraz best/current,
best-so-far, mean, median, worst, odchylenie standardowe, diversity,
evaluations i czas. Wynik końcowy zachowuje pełny genotyp długości 200 i SHA-256.

## 17. Kryterium sukcesu canary i pełnego pilota

`COMPLETED 0:0` jest konieczne, ale niewystarczające.

Canary ma potwierdzić:

- właściwy commit i czysty checkout na compute node;
- 9 przydzielonych węzłów i plan `431 available / 401 required Ray CPU`;
- sondę kodu/runtime oraz gotowy cache Matplotlib na każdym węźle;
- start head i wszystkich workerów Ray;
- 401 aktorów bez timeoutu startowego;
- torus 10×20 z dokładnie 200 wierzchołkami i poprawną adjacency;
- 200 kompletnych krótkich krzywych oraz zdarzenia migracji;
- `result_pointer.json`, manifesty i pełny kontrakt metryk;
- `State=COMPLETED`, `ExitCode=0:0`, marker `BENCHMARK_RUN_OK`.

Pełny pilot dodatkowo ma potwierdzić:

- trzy powtórzenia po 8000 ewaluacji/wyspę i 1996 kroków;
- 200 kompletnych wyników na powtórzenie;
- zgodność seedów/repeatów i hashy topologii;
- skończone wartości fitness oraz wszystkie końcowe genotypy;
- archiwum `raw_results.tar.gz` i poprawny `.sha256` dla każdego repeat;
- `pilot_summary.json` z `"valid": true` i `"valid_repeats": 3`;
- marker `PILOT_VALIDATION_OK` w logu finalizera;
- zapis `sacct`, rzeczywistych CPUh, `TotalCPU`, efektywności i `MaxRSS`, jeśli
  klaster zwróci metryki.

## 18. Struktura finalizowanego pilota

Docelowo:

```text
$SCRATCH/islandsEA/results/pilot_runs/<ARRAY_JOB_ID>/
├── submission.json
├── sacct.txt
├── pilot_summary.json
└── repeat-1..3/
    ├── attempt.json
    ├── result_pointer.json
    ├── raw_results.tar.gz
    ├── raw_results.tar.gz.sha256
    ├── ray_failure_logs/            # tylko po awarii
    └── verified/
        ├── validation.json
        ├── experiment_manifest.json
        ├── run_metadata.json
        ├── benchmark_manifest.json
        ├── topology.json
        ├── metrics_data_contract.json
        ├── analysis_summary.json
        └── wykresy PNG
```

Pobranie wykonuje się **na laptopie**, nie w shellu Aresa:

```powershell
cd C:\Users\piotr\UMISI\IslandsEA_summer\main_codebase\islandsEA_student_fork
.\pilot_run\download_pilot.ps1 -JobId ARRAY_JOB_ID
```

Cel:

```text
C:\Users\piotr\UMISI\IslandsEA_summer\artifacts\pilot_runs\<ARRAY_JOB_ID>
```

Helper ma sprawdzić trzy checksumy i `pilot_summary.json`. Dopiero
`PILOT_DOWNLOAD_OK` jest podstawą do rozważenia czyszczenia scratcha.

## 19. Storage, quota i ryzyko inode’ów

Migawka:

| Storage | Pojemność/limit | Użycie | Limit plików / użycie |
|---|---:|---:|---:|
| HOME | 10 GB | około 4.9–4.95 GB | 100 000 / około 67.7–67.9 tys. |
| SCRATCH | około 12 TiB hard limit | około 3 GB | 1 000 000 / około 78 252 |

`$PLG_GROUPS_STORAGE=/net/pr2/projects/plgrid`; `$PLG_GROUPS_SCRATCH` był pusty.
Repo i venv zostają w HOME, ale logi, JSON/CSV/NPY/Pickle, checkpointy,
archiwa, dumpy i stdout/stderr jobów mają trafiać na SCRATCH.

Obecny kontrakt generuje około 9 plików na wyspę plus pliki wspólne. Dla 180
wysp to około 1628–1629 plików/run; 1800 runów dałoby około 2.93 mln surowych
plików. To przekracza limit miliona inode’ów scratcha, nawet jeśli bajtowo dane
się mieszczą.

Kampania musi więc działać falami:

1. ograniczona liczba równoległych runów;
2. walidacja zakończonego runa;
3. jedno archiwum plus checksum;
4. pobranie/backup;
5. dopiero potem kontrolowane usunięcie rozpakowanych danych;
6. pomiar `du` i liczby plików po każdej fali.

Nie usuwać surowych danych automatycznie w tej samej transakcji, która tworzy
archiwum. Błąd archiwizacji lub transferu nie może pozostawić jedynej kopii
niekompletną.

## 20. Koszt pilota i kampanii 1800 runów

Macierz badań:

```text
5 topologii × 3 strategie × 40 benchmarków × 3 powtórzenia = 1800 runów
```

Przy 8000 ewaluacji na wyspę:

| Wyspy | Ewaluacje/run | Ewaluacje/1800 |
|---:|---:|---:|
| 150 | 1 200 000 | 2.16 mld |
| 180 | 1 440 000 | 2.592 mld |
| 200 | 1 600 000 | 2.88 mld |

Roboczy koszt przy pełnych węzłach:

| Średni walltime/run | 150 wysp, 336 CPU | 180 wysp, 384 CPU | 200 wysp, 432 CPU |
|---:|---:|---:|---:|
| 5 min | 50 400 CPUh | 57 600 CPUh | 64 800 CPUh |
| 10 min | 100 800 CPUh | 115 200 CPUh | 129 600 CPUh |
| 15 min | 151 200 CPUh | 172 800 CPUh | 194 400 CPUh |
| 30 min | 302 400 CPUh | 345 600 CPUh | 388 800 CPUh |
| 60 min | 604 800 CPUh | 691 200 CPUh | 777 600 CPUh |

To scenariusze, nie prognozy. Należy dodać co najmniej 20% na walidacje,
rozrzut i awarie. Rzetelna estymacja wymaga kilku pełnych pilotów obejmujących
szybkie i wolne problemy, różne rodziny benchmarków oraz skrajne strategie.

Po pilotach:

```bash
python smoke_run/slurm_job_cost.py JOB_ID_1 JOB_ID_2 JOB_ID_3 \
  --planned-runs 1800 \
  --overhead-percent 20 \
  --json-output "$SCRATCH/islandsEA/results/diagnostics/job_cost_pilots.json"
```

Pozostały budżet grantu CPU nie został potwierdzony przez diagnostykę. Przed
kampanią trzeba go odczytać z PLGrid. `MaxSubmitJobs=1000` oznacza też, że nie
wysyłamy array 1800 naraz; stosujemy fale wyraźnie poniżej limitu.

## 21. Topologie i nierozwiązany problem porównywalności

Aktualny stan:

| Topologia | Liczba wysp |
|---|---|
| `complete` | dowolne dodatnie N |
| `ring` | praktycznie N≥3; istniejący graf zawiera self-neighbour |
| historyczny `torus` | N≥24 i podzielne przez 12: 156, 168, 180, 192 w zakresie |
| jawny torus | `rows × columns = N`, np. 10×20 dla 200 |
| `er1`–`er4` | stałe grafy 150 |
| `ws3`, `ws4` | stałe grafy 144 |
| stare `er`, `ws`, `ws1`, `ws2` | nieużywać; pliki są stale/broken |

Nie ma obecnie pięciu topologii przy wspólnym N=150–200 bez zmiany aparatury.
Porównanie ER150 z WS144 i torusem200 miesza efekt topologii z liczbą wysp.
Najczystsze rozwiązanie to uzgodnić wspólne N, wygenerować raz stałe grafy,
zapisać adjacency w repo i hashować je w manifestach. Nie generować losowego
grafu podczas każdego joba.

Trzeba też zamrozić znaczenie „3 strategii”. Obecny pilot interpretuje je jako
strategie **wyboru** migrantów (`best` jako pierwszy wariant), z `plain` jako
stałym baseline'em przyjęcia. Jeśli macierz ma oznaczać trzy pary
selection/acceptance, manifest i plan 1800 konfiguracji muszą to wyrazić jawnie.

## 22. Bezpieczny workflow po wdrożeniu naprawy

Poniższy workflow jest właściwy dopiero na nowym, zweryfikowanym commicie.

Na laptopie:

1. zmiana kodu i testy nieobliczeniowe;
2. ręczny `git commit` i `git push` wykonany przez użytkownika;
3. brak benchmark compute lokalnie.

Na Aresie:

```bash
cd "$HOME/islandsEA_student_fork"
git switch summer_benchmarks
git pull --ff-only origin summer_benchmarks
git status --short --branch
git log -1 --oneline
```

`git status --short` musi być pusty. Następnie walidacja i małe runy:

```bash
bash hpc_benchmarks/submit_validation.sh

bash hpc_benchmarks/submit_ares.sh \
  --problem b03_nk_k4 --dimension 60 --islands 2 --evaluations 128 \
  --topology complete --strategy maxDistance --acceptance plain

bash hpc_benchmarks/submit_ares.sh \
  --problem r29_composition7 --dimension 200 --islands 2 --evaluations 128 \
  --topology complete --strategy best --acceptance plain
```

Po sukcesie testów ścieżki i po ponownym przeglądzie kosztu:

```bash
bash pilot_run/launch_pilot.sh --confirm-torus200-and-722-cpuh
```

Launcher ma wypisać nowe ID canary i gate. Starych `21059904/21059905` nie
można użyć jako dowodu zaliczonego canary.

## 23. Monitorowanie i diagnostyka

`squeue` pokazuje tylko aktualną kolejkę. Zakończony job znika z niego szybko;
to nie znaczy, że job się nie wykonał.

```bash
squeue -j JOB_ID -o "%.18i %.24j %.10T %.10M %.10l %R"

sacct -j JOB_ID -P \
  --format=JobIDRaw,JobName,Partition,Account,State,ExitCode,Elapsed,AllocCPUS,CPUTimeRAW,TotalCPU,MaxRSS,ReqMem,NodeList
```

Logi pilota:

```text
$SCRATCH/islandsEA/logs/slurm/pilot-canary-<JOB>.out/.err
$SCRATCH/islandsEA/logs/slurm/pilot-gate-<JOB>.out/.err
$SCRATCH/islandsEA/logs/slurm/pilot-<ARRAY>_<TASK>.out/.err
$SCRATCH/islandsEA/logs/slurm/pilot-finalize-<JOB>.out/.err
```

Po błędzie sprawdzić kolejno:

1. `sacct` dla joba i kroków `.batch`;
2. stderr i stdout SLURM;
3. `pipeline_submission.json`, `attempt.json`, `result_pointer.json`;
4. `$SCRATCH/islandsEA/logs/ray_failures/...`;
5. czy `ISLANDS_PROJECT_DIR`, commit i storage są zgodne;
6. dopiero potem logi `session_latest` Ray.

Pełna diagnostyka:

```bash
cd "$HOME/islandsEA_student_fork/smoke_run"
bash collect_ares_info.sh JOB_ID_1 JOB_ID_2
```

Dashboard Ray nie jest wymagany do poprawnego pilota. Nie instalować innej
wersji Ray tylko dla UI w produkcyjnym venv bez pełnej rewalidacji środowiska.

## 24. Reguły bezpieczeństwa

- Nie wykonywać benchmarków na laptopie ani login node.
- Nie ponawiać automatycznie awarii; najpierw klasyfikacja przyczyny.
- Nie wysyłać pełnego array bez zaliczonego canary tej samej konfiguracji i
  przypiętego commita.
- Nie ufać samemu `COMPLETED`; wymagać markerów, manifestów i walidacji danych.
- Nie lokalizować repo z `BASH_SOURCE` wewnątrz batch scriptu.
- Nie używać względnych ścieżek do kodu w jobie.
- Nie zapisywać dużych/generowanych danych do HOME lub repo.
- Nie używać wspólnego NFS jako katalogu sesji Ray.
- Nie używać legacy `run150*.sh`/`start_bm.py`; część ma stary kontrakt,
  brakujące pliki lub osiem zamiast dziewięciu argumentów.
- Nie zmieniać semantyki migracji, kolejności kolejki, topologii, seedów ani
  rezerwacji aktorów bez odnotowania wpływu na porównywalność.
- Nie usuwać znaku delay i nie zastępować surowej telemetrii wyłącznie agregatem.
- Nie usuwać danych ze scratcha przed pobraniem i weryfikacją checksum.
- Nie robić commitów/pushów w imieniu użytkownika bez jawnej prośby.

## 25. Zadanie dla następnej sesji Codexa

Kolejność pracy:

1. potwierdzić branch `summer_benchmarks` i czyste drzewo;
2. naprawić przekazywanie `ISLANDS_PROJECT_DIR` w całym pipeline, nie tylko w
   canary;
3. dodać testy regresyjne imitujące wykonanie ze spool;
4. sprawdzić wszystkie `BASH_SOURCE` w plikach wykonywanych bezpośrednio przez
   `sbatch`;
5. uruchomić testy lokalne/statyczne bez benchmark compute;
6. przekazać użytkownikowi diff — bez automatycznego commita;
7. po push/pull przeprowadzić małą walidację SLURM;
8. uruchomić nowy canary 200 wysp i zebrać komplet dowodów;
9. pozwolić gate wysłać trzy powtórzenia tylko po ścisłej walidacji;
10. po pilocie zaktualizować ten dokument o realny walltime, CPUh, MaxRSS,
    objętość danych, liczbę plików i ID jobów.

## 26. Warunek gotowości do kampanii

Pełne 1800 runów można planować dopiero, gdy jednocześnie:

- błąd spool został naprawiony i zabezpieczony testem;
- canary 200 wysp przeszedł na Aresie;
- pełny pilot trzech powtórzeń ma `valid_repeats=3`;
- wyznaczono rzeczywiste walltime, CPUh, MaxRSS, rozmiar i inode’y;
- potwierdzono pozostały grant CPU;
- zatwierdzono wspólne N, pięć topologii i trzy warianty strategii;
- wygenerowano jawny manifest całej macierzy i seedów;
- ustalono bezpieczną wielkość fal poniżej limitu submitów;
- działa archiwizacja, checksumy, pobieranie i retencja danych;
- istnieje procedura zatrzymania kampanii po wzroście błędów lub kosztu.

Do tego czasu infrastruktura jest wartościowym prototypem z potwierdzonym
smoke'em, ale nie jest jeszcze produkcyjnie gotowym mechanizmem masowego
uruchomienia.
