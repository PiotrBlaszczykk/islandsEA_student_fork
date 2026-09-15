> **Aktualizacja badania: 144 wyspy (mail 2026-09-15).**
> Aktualne instrukcje: [STUDY_144.md](../STUDY_144.md). Obowiązują torus12×12,
> complete, WS3 i BA z załączników. Dostarczony ER4 ma 150 węzłów i jest
> zablokowany dla badania144 do rozstrzygnięcia. Ares: 7×48=336CPU,
> wymagane289Ray+driver; pilot≤561.5CPUh, `--confirm-144-and-562-cpuh`.
> Athena: te same grafy144; pełny runner wysp GPU nadal wymaga integracji.
>
> **Poniżej zachowano historyczną migawkę debugowania i planów.** Liczby
> 150/180/200 dotyczące wysp, stare profile `*_ares_200.sh`, kształt10×20,
> CONFIRM_TORUS_200 i dawne polecenia uruchomienia zostały zastąpione.
> Nie używać ich jako aktualnej instrukcji. Historyczne joby, rachunki i pomiary
> zachowano bez przepisywania; D=200 nadal jest poprawnym wymiarem benchmarku.

# Athena / Cyfronet — stan środowiska i plan portu IslandsEA

Ostatnia aktualizacja: **2026-09-14**  
Użytkownik: `plgblaszczykk`  
Docelowy grant: **`plgintobl-gpu-a100`**  
Cel dokumentu: trwały handoff dla kolejnych sesji przygotowujących osobny,
rzeczywiście GPU-enabled profil IslandsEA na superkomputerze Athena.

> **Aktualizacja po readiness jobie `3167902`:** nowsze fakty numeryczne są w
> `ATHENA_CONFIG.md`, `ATHENA_GPU_PORT_HANDOFF.md` i
> `athena_kolejne_logi.txt`. Job zakończył się `COMPLETED 0:0` w 28 sekund,
> zainstalował `cupy-cuda117==10.6.0`, wykonał prawdziwy kernel
> `r01_elliptic` D=200 na A100, potwierdził zgodność CPU/GPU oraz skuteczne capy
> Ray 96 GiB + 8 GiB object store. Wcześniejsze fragmenty tego dokumentu o
> braku CuPy/kernela opisują stan historyczny sprzed joba `3167902`.

## 1. Stan w skrócie

- Athena jest dostępna, a konto `plgintobl-gpu-a100` jest aktywne i dozwolone
  na partycji `plgrid-gpu-a100`.
- Grant ma nominalnie `5000 GPUh`; diagnostyka v4 pokazała zużycie `114.02 GPUh`,
  czyli około **4885.98 GPUh pozostałego budżetu** (`97.72%`). Jest to migawka
  z `2026-09-13`, nie licznik czasu rzeczywistego.
- Bieżący fairshare wybranego konta wynosił `0.861837`, czyli nadal był dobry.
  Fairshare zmienia się wraz z użyciem i nie gwarantuje czasu startu.
- Repo na Athenie było czyste na branchu `summer_benchmarks_athena`, commit
  `0783da0146c9b01d1912e7146b6ce69c73440213` (`athena analysis 2`).
- Świeży venv `/net/people/plgrid/plgblaszczykk/venvs/islands-ray` został
  utworzony na compute node Atheny z modułu `Python/3.10.4`. Importy zależności
  przeszły i zakończyły się markerem `ATHENA_VENV_READY=1`.
- Na login node nie ma `nvidia-smi` ani `nvcc`; jest to oczekiwane i nie mówi
  nic o widoczności GPU wewnątrz alokacji.
- Pierwsza sonda GPU `3167364`, zgłoszona omyłkowo na koncie
  `plglscclass26-gpu-a100`, została anulowana przez użytkownika przed
  uruchomieniem: `CANCELLED by 117049`, `ElapsedRaw=0`, `AllocCPUS=0`,
  `CPUTimeRAW=0`. Nie zużyła zasobów obliczeniowych.
- Finalna sonda `3167517` zakończyła się `COMPLETED 0:0` w 15 sekund na
  `t0020`, z alokacją 1× A100, 16 CPU i 125 GiB RAM. Marker
  `ATHENA_GPU_PROBE_COMPLETE=1` jest obecny.
- Ray 2.9.3 autodetekuje `GPU: 1` oraz `accelerator_type:A100`; aktor
  `num_gpus=1` otrzymał `ray_gpu_ids=[0]`, `CUDA_VISIBLE_DEVICES=0` i poprawnie
  wykonał `nvidia-smi` na przydzielonej karcie.
- Potwierdzony sprzęt to `NVIDIA A100-SXM4-40GB`, 40960 MiB, compute capability
  8.0, sterownik `595.71.05`; `nvidia-smi` raportuje kompatybilność CUDA 13.2.
- Dla Ray na Athenie obowiązuje krótki `_temp_dir=/tmp/r${SLURM_JOB_ID}` z
  powodu limitu 107 bajtów dla socketów AF_UNIX.
- Ray nie respektuje automatycznie limitu pamięci joba: przy alokacji 125 GiB
  zaraportował około 776 GB pamięci i 200 GB object store. Produkcyjne
  launchery muszą jawnie ograniczać pamięć Ray/object store.
- Obecny IslandsEA jest obciążeniem **CPU** (Ray + jMetalPy/NumPy). Samo
  przydzielenie A100 nie daje akceleracji i nie jest wystarczającym powodem do
  uruchamiania produkcji na Athenie. Najpierw trzeba zaprojektować oraz
  zwalidować rzeczywiste użycie GPU.

Wniosek: infrastruktura konta, partycji i storage jest rozpoznana, ale port
wykonawczy nie jest jeszcze gotowy. Na Athenie nie uruchamiać obecnego pilota
Aresa ani kampanii 1800 runów.

## 2. Źródła i zakres pewności

Źródła:

- `main_codebase/athena-diagnostics_v2.txt` — starszy raport utworzony na
  `login01.athena.cyfronet.pl` 2026-09-13 o 21:38 CEST;
- `main_codebase/athena_diagnostics_v3.txt` — migawka z
  2026-09-14 02:21 CEST; zawiera gotowy venv i zgłoszenie sondy `3167517`, ale
  nadal nie zawiera dopisanej sekcji compute-node;
- `main_codebase/athena_diagnostics_v4.txt` — kompletny raport z finalną sekcją
  compute-node oraz markerem zakończenia sondy `3167517`; źródło nadrzędne;
- `main_codebase/athena_kolejne_logi.txt` — JSON i log numerycznego readiness
  joba `3167902`;
- `main_codebase/ATHENA_GPU_PORT_HANDOFF.md` — aktualne instrukcje dla portu
  40 benchmarków i integracji z IslandsEA;
- `main_codebase/athena_diagnostics.txt` — starsza migawka z 20:37 CEST;
- `hpc-grants`, `hpc-fs`, `sinfo`, `scontrol`, `sacctmgr` i `sshare` zawarte w
  raporcie;
- `AGENTS.md` oraz kod brancha `summer_benchmarks_athena`;
- ręczne wyniki z alokacji `3167422` na compute node `t0018`;
- [oficjalna dokumentacja Atheny](https://docs.hpc.cyfronet.pl/supercomputers/athena/);
- [dokumentacja kont i grantów](https://docs.hpc.cyfronet.pl/environment/batch-system/accounts-and-grants/).

Raport v4 obejmuje login node i compute node. Potwierdza sprzęt, sterownik,
NVLink, NUMA, InfiniBand, `CUDA_VISIBLE_DEVICES` oraz wykrywanie GPU przez Ray.
Nie potwierdza jeszcze działania kerneli obliczeniowych, ponieważ w venvie nie
ma frameworka GPU. Dane o kolejce, stanach węzłów, fairshare, zużyciu grantu i
przestrzeni dyskowej pozostają migawką.

## 3. Ścieżki i workflow

### Athena

```text
HOME:               /net/people/plgrid/plgblaszczykk
repo:               $HOME/islandsEA_student_fork
branch:             summer_benchmarks_athena
venv:               $HOME/venvs/islands-ray        # utworzony na Athenie
SCRATCH:            /net/tscratch/people/plgblaszczykk
root eksperymentów: $SCRATCH/islandsEA
wyniki:             $SCRATCH/islandsEA/results
logi SLURM:         $SCRATCH/islandsEA/logs/slurm
diagnostyka remote: $HOME/artifacts/athena_duagnostics.txt
```

Pisownia `athena_duagnostics.txt` w ścieżce zdalnej jest historycznym typo
ustalonym przy tworzeniu collectora. Lokalna kopia źródłowa tego dokumentu ma
poprawną nazwę `main_codebase/athena_diagnostics.txt`.

### Laptop

```text
repo:   C:\Users\piotr\UMISI\IslandsEA_summer\main_codebase\islandsEA_student_fork
raport: C:\Users\piotr\UMISI\IslandsEA_summer\main_codebase\athena_diagnostics_v4.txt
handoff:C:\Users\piotr\UMISI\IslandsEA_summer\main_codebase\ATHENA_INFO.md
wyniki: C:\Users\piotr\UMISI\IslandsEA_summer\artifacts
```

Zakładany przepływ pozostaje taki sam jak dla Aresa:

1. modyfikacje oraz testy statyczne na laptopie, bez lokalnego compute;
2. commit i push wykonywany przez użytkownika;
3. `git pull --ff-only` na Athenie;
4. mały, limitowany job diagnostyczny lub canary przez SLURM;
5. dane robocze na `$SCRATCH/islandsEA`, finalizacja i checksumy;
6. pobranie ważnych wyników do lokalnego `artifacts` przed czyszczeniem lub
   automatycznym wygaśnięciem danych na scratchu.

Nie hardcodować `/net/tscratch/...`; używać `$SCRATCH`. Ścieżka scratch Atheny
różni się od Aresa (`/net/afscra/...`).

## 4. Wybrany grant

| Pole | Wartość |
|---|---|
| Grant | `plgintobl` |
| Konto SLURM | `plgintobl-gpu-a100` |
| Zasób | `gpu-a100` |
| Status | active |
| Okres | 2026-05-06 — 2027-05-05 |
| Budżet | 5000 GPUh |
| Zużycie w raporcie | 114.02 GPUh |
| Pozostało z różnicy | około 4885.98 GPUh |
| Grupa | `plggiobl` |
| Członkowie | `plgblaszczykk`, `plglkwinta`, `plgolekb` |
| QOS | `normal` |
| Fairshare w raporcie | `0.861837` |

Użytkownik ma również dostęp do `plglscclass26-gpu-a100`, lecz nie jest to
konto wybrane dla tego projektu. W submitterach Athena domyślne konto ma być
`plgintobl-gpu-a100`; nie polegać na `DefaultAccount`, który w raporcie nadal
wskazywał `plglscclass26-gpu-a100`.

Przed większą falą zawsze wykonać:

```bash
hpc-grants
sshare -l -u "$USER"
```

Pozostały budżet jest współdzielony z grupą, więc różnica `5000 - 114.02` nie
jest rezerwacją wyłącznie dla jednego użytkownika.

## 5. System, SLURM i sprzęt

### Login node

| Element | Wartość |
|---|---|
| Host | `login01.athena.cyfronet.pl` |
| System | Rocky Linux 9.8 |
| Kernel | `5.14.0-687.42.1.el9_8.x86_64` |
| glibc | `2.34` |
| Widoczne CPU | 32 wirtualne AMD EPYC-Rome |
| RAM | około 251 GiB |
| Limit otwartych plików | 32768 |

Login node służy tylko do przygotowania i zgłaszania jobów. Nie uruchamiać na
nim testów Ray, ewaluacji benchmarków ani instalacji wymagającej kompilacji.

### SLURM

| Element | Wartość |
|---|---|
| Wersja | `23.11.7` |
| Partycja produkcyjna | `plgrid-gpu-a100` |
| Domyślny czas partycji | 15 minut |
| Maksymalny czas | 48 godzin |
| Liczba węzłów partycji | 48 |
| Łączne CPU | 6144 |
| Łączne GPU | 384 |
| MaxArraySize | 20001 |
| MaxJobCount | 100000 |
| Selekcja | `select/cons_tres`, `CR_CPU_MEMORY` |
| Izolacja | `task/cgroup,task/affinity` |

Każdy job ma jawnie podawać `--account`, `--partition`, `--gres`, CPU, RAM i
walltime. Nie polegać na domyślnych 15 minutach ani domyślnej partycji
`gpu-a100`.

### Węzeł produkcyjny A100

| Zasób | Wartość |
|---|---:|
| CPU | 128 rdzeni, 2× AMD EPYC 7742 |
| RAM raportowany przez SLURM | 1024000 MB |
| GPU | 8× NVIDIA A100-SXM4-40GB |
| Proporcja na 1 GPU | 16 CPU i 128000 MB RAM |
| GRES | `gpu:a100:8` |

Ręczna alokacja jednej karty na `t0018` potwierdziła:

```text
CUDA_VISIBLE_DEVICES=0
GPU=NVIDIA A100-SXM4-40GB
VRAM=40960 MiB
UUID=GPU-5b3e9978-aa4c-8fe4-4c90-2afca2e532b9
driver=595.71.05
```

Finalna sonda na `t0020` potwierdziła dodatkowo compute capability 8.0,
persistence mode, limit mocy 400 W, dwanaście aktywnych łączy NVLink po
25 GB/s oraz mapowanie karty do NUMA node 2. Job dostał 16 logicznych CPU w
ramach affinity, mimo że `lscpu` i `os.cpu_count()` pokazują cały węzeł (128).
Launchery muszą zatem bazować na `SLURM_CPUS_PER_TASK`, a nie `os.cpu_count()`.

Węzeł ma cztery aktywne interfejsy InfiniBand (`ib0`–`ib3`); Ray wybrał adres
`172.23.16.20` z `ib0`. Przed profilem wielowęzłowym trzeba jawnie ustalić
interfejs/adres head node i wykonać osobny test komunikacji między węzłami.

Wagi TRES partycji:

```text
cpu=0.0625
mem=0.0078125G
GRES/gpu=1
```

Nie wyprowadzać ostatecznego kosztu wyłącznie z wag. Po jobie sprawdzać
`AllocTRES`, `ReqTRES`, `billing` i faktyczne zużycie pokazywane przez
`hpc-grants`/portal.

Migawka stanów 48 unikalnych węzłów w raporcie:

```text
29 × mix
 6 × alloc
13 × fail*
 0 × idle
```

To wyjaśnia potencjalnie długie kolejki i pokazuje chwilowo zdegradowaną
dostępność, ale nie jest trwałą charakterystyką klastra. Przed każdym większym
submittem sprawdzić świeże `sinfo`.

`plgrid-now` miało limit 1 godziny i widziało tylko część węzłów. Używać go
wyłącznie do świadomie małych testów, jeśli konto jest dozwolone; podstawowym
celem pozostaje `plgrid-gpu-a100`.

## 6. Moduły i środowisko Pythona

Na login node nie było załadowanych modułów. Dostępne były między innymi:

- `Python/3.10.4`;
- CUDA od `10.0.130` do `12.8.0`;
- GCC/GCCcore 10–14;
- cuDNN dla wielu wersji CUDA, do `cuDNN/9.2.1.18-CUDA-12.4.0`;
- NVHPC z wariantami CUDA;
- `PyTorch-Geometric/2.5.1`.

Nie należy wybierać najnowszego CUDA w ciemno. Wersję trzeba dopasować do
sterownika widocznego na compute node oraz wybranej biblioteki GPU.

Sterownik `595.71.05` raportuje przez `nvidia-smi` `CUDA Version: 13.2`, co
oznacza poziom kompatybilności sterownika, a nie zainstalowany toolkit.
W finalnej sondzie nie załadowano modułu CUDA, dlatego `nvcc` był niedostępny
(`COMMAND_FAILED exit=1`). To jedyny błąd komendy w raporcie i jest oczekiwany.
Moduły toolkitu są dostępne do `CUDA/12.8.0`; właściwy wariant wybiera się pod
konkretny wheel/backend, a nie na podstawie samego numeru z `nvidia-smi`.

Aktualny stan venv:

```text
/net/people/plgrid/plgblaszczykk/venvs/islands-ray/bin/python: READY
Python module: Python/3.10.4
Ray: 2.9.3
scikit-learn: 1.1.3
setuptools: 58.1.0
verification: ATHENA_VENV_READY=1
```

Venv utworzono od zera na compute node, a nie skopiowano binarnie z Aresa.
`setuptools==58.1.0` spełnia ograniczenie `<81`. Nadal nie wybrano ani nie
zainstalowano backendu wykonującego ewaluacje na GPU. Przy następnym jobie
zapisać pełne `pip freeze` i wynik `pip check` do artefaktów diagnostycznych.

Na login i compute node `pip check` zwrócił `No broken requirements found`.
Nie są zainstalowane: PyTorch, CuPy, TensorFlow, JAX/JAXlib ani Numba.

## 7. Storage i quota

Wartości użytkownika z `hpc-fs`:

| Przestrzeń | Zajęte | Limit | Pliki | Limit plików |
|---|---:|---:|---:|---:|
| `$HOME` | około 1.177 GiB | 10 GiB | 48586 | 100000 |
| `$SCRATCH` | około 2.9 MiB | 12 TiB | brak świeżej liczby w v4 | 1000000 |
| storage grupy `plgglscclass` | 78.80 GiB | 100 GiB | 321793 | brak użytecznego limitu w raporcie |
| storage grupy `plggiobl` | 11 KiB | 1 GiB | 1 | brak użytecznego limitu w raporcie |

Wybrana grupa `plggiobl` ma tylko 1 GiB trwałego storage, więc nie pomieści
kampanii. Surowe eksperymenty powinny trafiać do:

```text
$SCRATCH/islandsEA/
├── results/
├── logs/
├── checkpoints/
└── tmp/
```

Globalny filesystem `$SCRATCH` był zajęty w 91%, mimo że quota użytkownika była
prawie pusta. Należy monitorować zarówno `hpc-fs`, jak i `df -h "$SCRATCH"`.

Sam venv zajmuje około 889 MiB i podniósł użycie inode HOME do 48586, czyli
48.6% limitu 100000 plików. Nie instalować wielu równoległych kopii venva ani
cache pip w HOME; cache i generowane środowiska testowe kierować na scratch.

Athena traktuje scratch jako przestrzeń nietrwałą: dane starsze niż 30 dni i
katalogi jobów starsze niż 7 dni mogą zostać automatycznie usunięte. Finalne
wyniki trzeba archiwizować, hashować i regularnie pobierać na laptop. Repo oraz
mały venv mogą zostać w HOME; duże cache pakietów, logi Ray, wyniki i dumpy nie.

## 8. Status sond GPU

Pierwszy job `3167364` używał niewłaściwego konta
`plglscclass26-gpu-a100`. Został anulowany przed startem i według `sacct` nie
otrzymał CPU/GPU ani nie naliczył czasu.

Interaktywne joby `3167422`, `3167478` i `3167494` zakończyły się timeoutem.
Łącznie odpowiadają za około 0.844 GPUh. Były częścią ręcznej diagnostyki, nie
wynikiem algorytmu; nie powtarzać tego wzorca — używać krótkich jobów batch.

Finalna sonda:

```text
job:       3167517
account:   plgintobl-gpu-a100
partition: plgrid-gpu-a100
state:     COMPLETED
exit:      0:0
elapsed:   00:00:15
node:      t0020
GPU:       1
CPU:       16
RAM:       128000M
walltime:  00:10:00
marker:    ATHENA_GPU_PROBE_COMPLETE=1
```

Znane ścieżki:

```text
raport: $HOME/artifacts/athena_duagnostics.txt
stdout: $SCRATCH/islandsEA/logs/slurm/athena-diagnostics-3167517.out
stderr: $SCRATCH/islandsEA/logs/slurm/athena-diagnostics-3167517.err
```

Najważniejszy wynik Ray:

```text
Ray:                   2.9.3
cluster GPU:           1.0
accelerator type:      A100
cluster CPU:           16.0
actor ray_gpu_ids:     [0]
actor CUDA_VISIBLE:    0
actor nvidia-smi:      exit 0, właściwa A100
```

Sonda diagnostyczna jest zamknięta; nie zgłaszać kolejnej bez nowego pytania
diagnostycznego. Wykryty problem produkcyjny:

```text
SLURM memory allocation: 125 GiB
Ray memory resource:     775689550848 B (~722.4 GiB)
Ray object store:        200000000000 B (~186.3 GiB)
```

Ray 2.9.3 widzi pamięć całego hosta zamiast limitu joba. Cgroup SLURM pozostaje
ostatecznym limitem, więc bez jawnych capów proces może zostać ubity przez OOM.
Każdy launcher ma ustawiać `num_cpus` z `SLURM_CPUS_PER_TASK`, rozsądne
`object_store_memory` mieszczące się w przydziale oraz limit pamięci aplikacji.
Nie wyprowadzać limitów z `free`, `/dev/shm` ani `os.cpu_count()`.

## 9. Dlaczego profil Aresa nie pasuje do Atheny

Obecny model zasobów kodu rezerwuje:

- `N` aktorów `Island`, po 1 CPU;
- `N` aktorów `Computation`, po 1 CPU;
- 1 aktora `SignalActor`, 1 CPU;
- dodatkowo 1 CPU poza pulą Ray dla drivera.

Dla 200 wysp:

```text
Ray:      2*200 + 1 = 401 CPU
fizyczne: minimum 402 CPU z driverem
```

Na Athenie jedna A100 daje proporcjonalnie 16 CPU. Naiwne zachowanie obecnych
rezerwacji wymagałoby co najmniej:

```text
ceil(402 / 16) = 26 GPU
```

Ze względu na jednorodny przydział per node prosty profil czterowęzłowy mógłby
skończyć np. z 4×7 GPU i 4×112 CPU, czyli 28 A100 oraz 448 CPU. Przy limicie
30 minut dawałoby to do 14 GPUh na jedno powtórzenie i 42 GPUh na trzy
powtórzenia — mimo że aktualny algorytm praktycznie nie wykonywałby pracy na
GPU. To jest nieefektywne, kosztowne i sprzeczne z przeznaczeniem Atheny.

Nie wolno więc kopiować `run_ares_200.sh` i tylko dopisywać `--gres=gpu`.
Również arbitralne zmniejszenie `num_cpus` aktorów zmieni harmonogram wysp i
badane opóźnienia migracji, czyli semantykę eksperymentu.

## 10. Co musi oznaczać rzeczywisty port GPU

Przed kodowaniem należy wybrać i opisać model wykonania. Kandydaci:

1. GPU-owa, zbiorcza ewaluacja funkcji celu, współdzielona przez wiele wysp;
2. grupowanie kilku/kilkudziesięciu wysp na jeden GPU i batchowanie populacji;
3. jedna pula ewaluatorów GPU, podczas gdy logika GA i migracje pozostają w
   aktorach CPU;
4. inny jawnie uzgodniony podział, który rzeczywiście utrzymuje GPU zajęte.

Każdy wariant wymaga sprawdzenia:

- czy wszystkie 40 benchmarków mają zgodną implementację GPU i identyczną
  precyzję/liczbową semantykę;
- czy batching nie zmienia kolejności, czasu i asynchroniczności migracji;
- czy seedy, wyniki i tolerancje są zgodne z wersją CPU;
- ile wysp przypada na GPU;
- czy Ray poprawnie reklamuje `GPU`, respektuje `CUDA_VISIBLE_DEVICES` i nie
  oversubskrybuje kart;
- jaka jest przepustowość oraz narzut dla bardzo małych populacji (`16`,
  offspring `4`, wymiar `200`);
- jak zapisywać metadane backendu (`cpu/gpu`, model, UUID GPU, sterownik, CUDA,
  biblioteka, dtype) w `run_metadata.json`.

Małe batche obecnego algorytmu mogą być zbyt małe, aby zamortyzować koszt
uruchamiania kerneli GPU. To hipoteza do zmierzenia, nie założenie o
przyspieszeniu.

## 11. Zalecana kolejność dalszych działań

### Krok A — domknąć aktualną sondę

**Wykonane.** Job `3167517` zakończył się `COMPLETED 0:0`, raport v4 zawiera
marker i pełną sekcję compute-node.

### Krok B — utworzyć świeży venv Atheny

**Wykonane ręcznie.** Świeży venv powstał na compute node z
`Python/3.10.4`; importy zakończyły się `ATHENA_VENV_READY=1`. Do automatyzacji
pozostaje osobny skrypt SLURM, który na jednej A100:

1. ładuje ustalony moduł Python/CUDA;
2. tworzy `$HOME/venvs/islands-ray` albo wyraźnie nazwany venv Athena;
3. instaluje zgodny Ray/jMetalPy i wybrany backend GPU bez cache w HOME;
4. wykonuje `pip check`, zapisuje `pip freeze` i wersje runtime;
5. nie uruchamia jeszcze algorytmu.

Kompilację i instalację zależności binarnych wykonywać w jobie compute, nie na
login node.

### Krok C — minimalny smoke GPU

Warstwa SLURM + sterownik + Ray jest potwierdzona. Ray widzi A100, a aktor GPU
dostaje kartę. Brakuje jeszcze frameworka wykonującego rzeczywistą operację
numeryczną na GPU, więc ten podpunkt przechodzi do kroku D.

Warunki sukcesu:

- [x] `nvidia-smi` widzi dokładnie przydzieloną kartę;
- framework GPU wykonuje realną operację i synchronizację;
- [x] Ray raportuje `GPU: 1`;
- [x] task `@ray.remote(num_gpus=1)` widzi poprawne `CUDA_VISIBLE_DEVICES`;
- [x] katalog Ray ma krótką ścieżkę w node-local `/tmp`;
- [x] job kończy się `COMPLETED 0:0` i ma zmierzone `AllocTRES`/billing.

### Krok D — prototyp ewaluacji i porównanie CPU/GPU

Najpierw jedna funkcja ciągła i małe dane. Porównać wartości CPU/GPU na tych
samych wektorach, następnie throughput dla realistycznych batchy. Portować
pozostałe benchmarki dopiero po ustaleniu opłacalnego modelu batchowania.

### Krok E — mały Ray canary

Uruchomić kilka wysp na jednej karcie, sprawdzić migracje, metryki i zachowanie
asynchroniczne. Potem test dwuwęzłowy, który potwierdzi interfejs sieciowy oraz
start Ray między węzłami Atheny.

### Krok F — dopiero pilot 200 wysp

Przed submittem zamrozić liczbę GPU/węzłów, koszt maksymalny, mapping wysp,
backend i tolerancje numeryczne. Zachować tę samą bramkę canary, pin commita,
walltime, brak automatycznych retry oraz pełne metadane jak w pilocie Aresa.

## 12. Obsługa diagnostyki

Collector na branchu `summer_benchmarks_athena`:

```bash
cd "$HOME/islandsEA_student_fork"
git pull --ff-only origin summer_benchmarks_athena
bash athena_diagnostics/collect_athena_info.sh
```

Po aktualizacji kodu domyślnie używa:

```text
account=plgintobl-gpu-a100
partition=plgrid-gpu-a100
gres=gpu:1
cpus_per_task=16
memory=128000M
time_limit=00:10:00
```

Jawne wywołanie równoważne:

```bash
ATHENA_ACCOUNT=plgintobl-gpu-a100 \
  bash athena_diagnostics/collect_athena_info.sh
```

Sama diagnostyka login node, bez alokacji:

```bash
bash athena_diagnostics/collect_athena_info.sh --login-only
```

Pobranie pełnego raportu na laptop:

```powershell
cd C:\Users\piotr\UMISI\IslandsEA_summer\main_codebase\islandsEA_student_fork
.\athena_diagnostics\download_report.ps1 `
  -Destination C:\Users\piotr\UMISI\IslandsEA_summer\main_codebase\athena_diagnostics.txt
```

Downloader celowo odmawia sukcesu, jeżeli brakuje markera compute-node probe.

## 13. Reguły bezpieczeństwa

- Wszystkie joby Athena rozliczać z `plgintobl-gpu-a100`, chyba że użytkownik
  jawnie wskaże inny grant.
- Nie uruchamiać produkcji na GPU bez rzeczywistego użycia GPU.
- Nie uruchamiać obliczeń ani instalacji na login node.
- Nie przenosić binarnie venva Aresa na Athenę.
- Repo i małe configi pozostają w HOME; wyniki, logi, checkpointy, cache i dumpy
  idą do `$SCRATCH/islandsEA`.
- Ray, Matplotlib i cache frameworka GPU używają node-local `/tmp` w obrębie
  joba; cleanup musi sprawdzać dokładną ścieżkę.
- Każdy kosztowny etap ma canary, twardy walltime, jawny plan zasobów i brak
  automatycznego retry.
- Nie zmieniać semantyki migracji, kolejek ani akceptacji tylko po to, żeby
  łatwiej zmieścić kod na GPU.
- Nie wykonywać commitów ani pushy za użytkownika bez jawnego polecenia.

## 14. Otwarte kwestie / blokery

1. Który toolkit CUDA i backend GPU wybieramy: CuPy, PyTorch, JAX, Numba czy
   własne kernele?
2. Jak batchować ewaluacje bez zmiany semantyki asynchronicznego eksperymentu?
3. Jak jawnie ograniczyć pamięć Ray/object store do alokacji SLURM i dobrać
   bezpieczne wartości dla produkcji?
4. Ile GPU i węzłów rzeczywiście potrzeba dla 200 wysp po zmianie backendu?
5. Jaki jest zmierzony koszt GPUh, walltime, wykorzystanie GPU i MaxRSS pilota?
6. Gdzie długoterminowo przechowywać wyniki, skoro storage grupy `plggiobl` ma
   tylko 1 GiB, a scratch jest automatycznie czyszczony?

Podstawowa diagnostyka Atheny jest zakończona. Do czasu rozwiązania punktów 1–4
można bezpiecznie rozwijać backend i wykonywać małe, limitowane canary. Nie ma
jeszcze podstaw do uruchomienia pełnego pilota ani kampanii na Athenie.
