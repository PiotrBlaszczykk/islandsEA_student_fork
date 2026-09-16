> **Aktualizacja badania: 144 wyspy (mail 2026-09-15).**
> Aktualne instrukcje: [STUDY_144.md](../STUDY_144.md). Obowiązują torus12×12,
> complete, WS3 i BA z załączników. Dostarczony ER4 ma 150 węzłów i jest
> zablokowany dla badania144 do rozstrzygnięcia. Ares: 7×48=336CPU,
> wymagane289Ray+driver; pilot≤561.5CPUh, `--confirm-144-and-562-cpuh`.
> Athena: te same grafy144; shardowany runner GPU jest zaimplementowany lokalnie
> i wymaga pierwszego canary na A100 przed jednym normalnym runem.
>
> **Poniżej zachowano historyczną migawkę debugowania i planów.** Liczby
> 150/180/200 dotyczące wysp, stare profile `*_ares_200.sh`, kształt10×20,
> CONFIRM_TORUS_200 i dawne polecenia uruchomienia zostały zastąpione.
> Nie używać ich jako aktualnej instrukcji. Historyczne joby, rachunki i pomiary
> zachowano bez przepisywania; D=200 nadal jest poprawnym wymiarem benchmarku.

# IslandsEA na Athenie — konfiguracja, stan i projekt portu GPU

Ostatnia aktualizacja: **2026-09-14**  
Użytkownik PLGrid: `plgblaszczykk`  
Docelowy grant: `plgintobl-gpu-a100`  
Docelowy branch GPU: `summer_benchmarks_athena`  
Status: **Athena/F1 proof of concept zweryfikowane; batch CPU/CuPy dla 40 funkcji zaimplementowany i sprawdzony lokalnie na CPU; pełna walidacja A100 i integracja 200 wysp pozostają do wykonania**

Ten dokument jest branch-niezależnym handoffem dla kolejnych sesji Codexa.
Opisuje fakty potwierdzone na Athenie, bieżącą architekturę IslandsEA, wymagany
kształt implementacji GPU oraz warunki, które muszą być spełnione przed pilotem
200 wysp i przed kampanią 1800 uruchomień.

## 1. Najważniejsze rozróżnienie

Na Athenie działa już cały fundament operacyjny i numeryczny proof of concept:

```text
SLURM -> A100 -> venv -> Ray 2.9.3 -> aktor num_gpus=1 -> CuPy -> kernel F1
```

Job readiness `3167902` zainstalował przypięte `cupy-cuda117==10.6.0`, wykonał
na A100 wektorową wersję `r01_elliptic` w `float64`, porównał ją z publicznym
ewaluatorem CPU i potwierdził bezpieczne limity pamięci Ray. Nie oznacza to
jeszcze, że główny IslandsEA korzysta z GPU: produkcyjna ścieżka nadal ewaluuje
problemy przez jMetalPy i NumPy na CPU. Proof of concept znajduje się w
`athena_gpu/gpu_readiness.py`, poza właściwym tokiem algorytmu.

Stan należy interpretować następująco:

| Warstwa | Stan |
|---|---|
| Konto, grant, partycja | zweryfikowane |
| Przydział 1× A100 przez SLURM | zweryfikowany |
| Python/venv na compute node | zweryfikowane |
| Ray wykrywa A100 | zweryfikowane |
| Aktor Ray dostaje przydzielone GPU | zweryfikowane |
| Framework numeryczny GPU | CuPy `10.6.0`, CUDA runtime `11.7`, zweryfikowane |
| `r01_elliptic`, D=200, GPU | kernel i zgodność CPU/GPU zweryfikowane |
| 40 benchmarków na GPU | backend CuPy zaimplementowany; pełna walidacja A100 jeszcze niewykonana |
| 40 benchmarków NumPy batch | 170 instancji przeszło lokalną walidację CPU, raport `athena_gpu/validation_cpu.json` |
| Batchowanie ewaluacji wielu wysp | niezaimplementowane |
| Bezpieczne limity Ray | 16 CPU, 1 GPU, 96 GiB heap, 8 GiB object store — zweryfikowane |
| Mapowanie 200 wysp na GPU | do zaprojektowania i zmierzenia |
| Pilot 200 wysp na Athenie | niedopuszczony |
| Kampania 1800 runów na Athenie | niedopuszczona |

W tym projekcie przewaga czasowa nad Aresem **nie jest warunkiem użycia
Atheny**. Ares jest obecnie trudno dostępny, a grant A100 jest przeznaczony dla
tego zespołu. Bramkami pozostają: poprawność naukowa, brak awarii/OOM,
rzeczywiste wykonywanie pracy na GPU, rozsądna agregacja małych ewaluacji,
pełne metadane i kontrolowany koszt. Pomiary CPU/GPU służą do dobrania
architektury i uniknięcia bezczynnej karty, a nie do odrzucenia Atheny.

## 2. Źródła prawdy

Najważniejsze lokalne pliki:

- `C:\Users\piotr\UMISI\IslandsEA_summer\main_codebase\athena_diagnostics_v4.txt`
  — kompletny raport login node + compute node; nadrzędne źródło sprzętowe;
- `C:\Users\piotr\UMISI\IslandsEA_summer\main_codebase\athena_kolejne_logi.txt`
  — pełny wynik readiness joba `3167902`, w tym JSON, czasy i markery;
- `C:\Users\piotr\UMISI\IslandsEA_summer\main_codebase\ATHENA_GPU_PORT_HANDOFF.md`
  — wykonawczy handoff dla sesji portującej 40 benchmarków;
- `C:\Users\piotr\UMISI\IslandsEA_summer\main_codebase\ATHENA_INFO.md`
  — szerszy raport środowiskowy i historia diagnostyki;
- `C:\Users\piotr\UMISI\IslandsEA_summer\main_codebase\islandsEA_student_fork\AGENTS.md`
  — ogólne kompendium projektu i reguły bezpieczeństwa;
- `athena_diagnostics/collect_athena_info.sh` oraz
  `athena_diagnostics/run_gpu_probe.sh` na branchu `summer_benchmarks_athena`;
- oficjalna dokumentacja:
  [Athena](https://docs.hpc.cyfronet.pl/supercomputers/athena/) oraz
  [konta i granty](https://docs.hpc.cyfronet.pl/environment/batch-system/accounts-and-grants/).

Zdalny raport collectora jest przechowywany pod historyczną, błędnie napisaną
nazwą:

```text
$HOME/artifacts/athena_duagnostics.txt
```

Nie poprawiać tej nazwy tylko w jednym miejscu. Ewentualna zmiana wymaga
jednoczesnej aktualizacji collectora, downloadera i dokumentacji.

## 3. Separacja branchy i klastrów

| Obszar | Branch | Przeznaczenie |
|---|---|---|
| Ares | `summer_benchmarks` | CPU, obecny pilot i kampania CPU |
| Athena | `summer_benchmarks_athena` | diagnostyka i przyszły port GPU |

Reguły:

1. Nie kopiować launchera Aresa na Athenę przez samo dodanie `--gres=gpu`.
2. Nie wprowadzać eksperymentalnego backendu GPU na `summer_benchmarks`, dopóki
   nie zostanie osobno zwalidowany.
3. Przed każdą zmianą uruchomić `git branch --show-current` i `git status`.
4. Nie wykonywać commitów ani pushy za użytkownika bez jego jawnego polecenia.
5. Dokumenty `ATHENA_CONFIG.md` i `ATHENA_INFO.md` leżą obok repo, dzięki czemu
   są niezależne od przełączania branchy.

Migawka laptopa podczas tworzenia tego dokumentu wskazywała branch
`summer_benchmarks_athena` i czysty working tree. Stan należy zawsze sprawdzić
ponownie; nie zakładać go na podstawie historii rozmowy.

## 4. Ścieżki na Athenie

```text
HOME:               /net/people/plgrid/plgblaszczykk
repo:               $HOME/islandsEA_student_fork
venv:               $HOME/venvs/islands-ray
SCRATCH:            /net/tscratch/people/plgblaszczykk
root projektu:      $SCRATCH/islandsEA
wyniki:             $SCRATCH/islandsEA/results
logi:               $SCRATCH/islandsEA/logs
logi SLURM:         $SCRATCH/islandsEA/logs/slurm
checkpointy:        $SCRATCH/islandsEA/checkpoints
trwałe tmp projektu:$SCRATCH/islandsEA/tmp
krótkie tmp Ray:    /tmp/r${SLURM_JOB_ID}
raport diagnostyczny:$HOME/artifacts/athena_duagnostics.txt
```

Nie hardcodować `/net/tscratch/people/plgblaszczykk`. Korzystać ze zmiennej
`$SCRATCH`, ponieważ jej wartość różni się między Atheną i Aresem.

## 5. Grant i zasoby SLURM

Wybrany grant:

| Pole | Wartość |
|---|---|
| Grant | `plgintobl` |
| Konto SLURM | `plgintobl-gpu-a100` |
| Zasób | `gpu-a100` |
| Status w raporcie | active |
| Okres | 2026-05-06 — 2027-05-05 |
| Budżet | 5000 GPUh |
| Zużycie w migawce v4 | 114.02 GPUh |
| Pozostało z prostej różnicy | około 4885.98 GPUh |
| Grupa | `plggiobl` |
| QOS | `normal` |
| Fairshare w migawce | `0.861837` |

Zużycie i fairshare są współdzielone i zmienne. Przed większym etapem ponownie
sprawdzić `hpc-grants`, `sshare` i `squeue`.

Docelowa partycja:

```text
partition: plgrid-gpu-a100
account:   plgintobl-gpu-a100
```

Zasoby jednego węzła:

| Zasób | Wartość |
|---|---:|
| CPU | 128 × AMD EPYC 7742 |
| RAM raportowany przez SLURM | 1024000 MB |
| GPU | 8 × NVIDIA A100-SXM4-40GB |
| Zasób proporcjonalny do 1 GPU | 16 CPU + 128000 MB RAM |
| Maksymalny walltime partycji | 48 godzin |
| Domyślny walltime | 15 minut |

Każdy submitter musi jawnie podawać konto, partycję, `--gres`, CPU, RAM i
walltime. Nie polegać na wartościach domyślnych.

## 6. Finalna sonda GPU

Job diagnostyczny:

```text
job_id:      3167517
state:       COMPLETED
exit_code:   0:0
elapsed:     00:00:15
node:        t0020
account:     plgintobl-gpu-a100
partition:   plgrid-gpu-a100
allocation:  1 GPU, 16 CPU, 125 GiB RAM
marker:      ATHENA_GPU_PROBE_COMPLETE=1
```

Koszt wynikający z czasu ściennego jednej karty wyniósł około 0.0042 GPUh.

Potwierdzona karta:

```text
model:               NVIDIA A100-SXM4-40GB
VRAM:                40960 MiB
compute capability:  8.0
driver:              595.71.05
nvidia-smi CUDA:     13.2
persistence mode:    enabled
power limit:         400 W
CUDA_VISIBLE_DEVICES:0
```

`CUDA Version: 13.2` z `nvidia-smi` jest poziomem kompatybilności sterownika,
a nie potwierdzeniem zainstalowanego toolkitu CUDA 13.2.

Sonda potwierdziła 12 aktywnych łączy NVLink po 25 GB/s dla widocznej karty.
Karta była przypisana do NUMA node 2. Proces dostał affinity obejmujące 16 CPU,
choć `lscpu` i `os.cpu_count()` widziały cały 128-rdzeniowy host.

Wniosek: kod nie może wyprowadzać przydziału CPU z `os.cpu_count()`. Źródłem
prawdy jest `SLURM_CPUS_PER_TASK` i parametry alokacji.

### Numeryczny readiness test A100

Nowszy job `3167902` zamknął diagnostykę numeryczną:

```text
job_id:        3167902
commit:        6bbdedf609e3e8eebd01fdea3b8be39d365a5d80
state/exit:    COMPLETED / 0:0
elapsed:       00:00:28
node:          t0020
allocation:    1 A100, 16 CPU, 125 GiB RAM
backend:       cupy-cuda117==10.6.0
CUDA module:   CUDA/11.7.0
benchmark:     r01_elliptic, D=200, float64
Ray caps:      96 GiB heap, 8 GiB object store
Ray tmp:       /tmp/r3167902
cost:          około 0.0078 GPUh
```

Wszystkie markery zakończyły się sukcesem:

```text
ATHENA_CUPY_KERNEL_OK=1
ATHENA_R01_CPU_GPU_MATCH=1
ATHENA_RAY_MEMORY_LIMITS_OK=1
ATHENA_RAY_GPU_ACTOR_OK=1
ATHENA_GPU_READINESS_OK=1
```

Maksymalny błąd względny względem publicznego skalarnego ewaluatora CPU wyniósł
`2.8385929965389834e-16`. Maksymalny błąd bezwzględny `6.103515625e-05`
wynika ze skali wartości funkcji; test `rtol=1e-12`, `atol=1e-6` przeszedł.
Zweryfikowany hash danych instancji D=200 to
`86ac55435ea9b3cb55d9df5129055aa63911fcd96791efd1fda189f3c39e0f89`.

Pomiar pełnej ścieżki klient Ray → aktor GPU → klient:

| Batch | CPU eval/s | GPU przez Ray eval/s | GPU/CPU |
|---:|---:|---:|---:|
| 4 | 65 488 | 3 641 | 0.056× |
| 16 | 169 205 | 14 169 | 0.084× |
| 64 | 266 357 | 40 265 | 0.151× |
| 256 | 365 794 | 146 146 | 0.400× |
| 1024 | 454 488 | 392 102 | 0.863× |
| 4096 | 330 508 | 924 562 | 2.797× |

Dla batcha 4096 sam kernel osiągnął około `37.56 mln eval/s`, lecz pełny
roundtrip około `0.925 mln eval/s`. Oznacza to, że dominującym kosztem jest
orchestracja, serializacja i transfer, nie arytmetyka A100. Wynik nie jest
bramką „GPU musi pobić Aresa”; jest wytyczną, aby nie wykonywać jednego
zdalnego wywołania GPU dla każdego offspring batcha wielkości 4.

## 7. Sieć compute node

Na `t0020` były cztery aktywne interfejsy InfiniBand:

```text
ib0: 172.23.16.20
ib1: 172.23.17.20
ib2: 172.23.18.20
ib3: 172.23.19.20
```

Lokalny Ray wybrał `172.23.16.20`, czyli `ib0`. Nie uznawać tego za finalną
konfigurację wielowęzłową. Przed skalowaniem trzeba wykonać canary na dwóch
węzłach i jawnie zamrozić interfejs/adres head node, porty oraz sposób startu
workerów Ray.

## 8. Python i venv

Aktywacja na Athenie:

```bash
module load Python/3.10.4
source "$HOME/venvs/islands-ray/bin/activate"
```

Nazwa modułu ma duże `P`. Nie używać aresowego
`python/3.10.4-gcccore-11.3.0` w skryptach Atheny.

Zweryfikowane wersje:

| Pakiet | Wersja |
|---|---:|
| Python | 3.10.4 |
| Ray | 2.9.3 |
| jMetalPy | 1.5.5 |
| NumPy | 1.21.4 |
| SciPy | 1.7.3 |
| scikit-learn | 1.1.3 |
| pandas | 1.3.4 |
| matplotlib | 3.5.0 |
| setuptools | 58.1.0 |
| packaging | 21.3 |
| CuPy distribution | `cupy-cuda117` 10.6.0 |
| fastrlock | 0.8.3 |

`pip check` przeszedł na login i compute node. `setuptools==58.1.0` spełnia
ograniczenie `<81`. Job readiness zainstalował CuPy we wspólnym venvie pod
blokadą `flock`, zapisał `pip-freeze.txt` i ponownie wykonał `pip check`.
Kolejne joby mają wymagać dokładnie jednego pakietu CuPy:
`cupy-cuda117==10.6.0`; obecność innej lub mieszanej dystrybucji ma powodować
fail-fast. Nie instalować równolegle z wielu jobów ani tworzyć drugiej kopii
venva w HOME.

## 9. CUDA

Dostępne moduły toolkitu obejmowały wersje od `CUDA/10.0.130` do
`CUDA/12.8.0`. Dostępne były także warianty cuDNN i NVHPC.

Finalna sonda ładowała tylko `Python/3.10.4`, dlatego `nvcc` nie był dostępny.
`COMMAND_FAILED exit=1` w sekcji CUDA compiler jest oczekiwany i był jedynym
błędem pojedynczej komendy w kompletnym raporcie. Sterownikowe `libcuda.so`
było dostępne.

Dla obecnego proof of concept wybór został zamrożony na:

```text
module:       CUDA/11.7.0
distribution:cupy-cuda117==10.6.0
runtime CuPy: 11070
driver API:   13020
```

Ta kombinacja wykonała prawdziwy kernel na A100. Nie aktualizować CuPy ani CUDA
przy okazji portu kolejnych funkcji. Zmiana toolkitu/backendu wymaga osobnego
readiness joba, porównania CPU/GPU oraz nowego zapisu wersji w metadanych.

## 10. Ray: co zostało potwierdzone

Finalna sonda bez ręcznego `num_gpus` w `ray.init()` wykazała prawdziwą
autodetekcję:

```text
cluster_resources.GPU:             1.0
cluster_resources.CPU:             16.0
cluster_resources.accelerator_type:A100: 1.0
gpu_task.ray_gpu_ids:               [0]
gpu_task.CUDA_VISIBLE_DEVICES:      "0"
gpu_task.nvidia_smi_exit_code:      0
```

Aktor zadeklarowany jako `@ray.remote(num_gpus=1)` dostał właściwą kartę.
Nowszy job `3167902` dodatkowo potwierdził wykonanie kernela CuPy, kopiowanie
host↔device, synchronizację i zwrot wyniku przez Ray.

### Krótka ścieżka sesji Ray

Ray tworzy sockety UNIX wewnątrz `_temp_dir`. Długa ścieżka spowodowała:

```text
AF_UNIX path length cannot exceed 107 bytes
```

Na Athenie stosować:

```text
/tmp/r${SLURM_JOB_ID}
```

Nie stosować długich ścieżek zawierających nazwę użytkownika i projektu.
Cleanup może usuwać wyłącznie dokładnie zweryfikowaną ścieżkę odpowiadającą
`^/tmp/r[0-9]+$`.

### Krytyczna pułapka pamięci

Przy alokacji 125 GiB Ray 2.9.3 zaraportował:

```text
Ray memory resource: 775689550848 B (~722.4 GiB)
object store:        200000000000 B (~186.3 GiB)
```

Ray widział pamięć całego hosta, a nie limit joba. `/dev/shm` również pokazywał
zasób hosta. Cgroup SLURM jest ostatecznym limitem i może zabić proces przez OOM.

Readiness job potwierdził skuteczne rozwiązanie: `ray.init()` z
`num_cpus=16`, `num_gpus=1`, `_memory=96 GiB` oraz
`object_store_memory=8 GiB` zaraportował dokładnie te limity. W przyszłym
launcherze trzeba:

1. ustawić `num_cpus` z `SLURM_CPUS_PER_TASK`;
2. jawnie ograniczyć `object_store_memory` do bezpiecznej części alokacji;
3. zachować zweryfikowane jawne capy jako domyślną bezpieczną bazę i zmieniać
   je tylko po pomiarze canary;
4. nie wyprowadzać limitu z `free`, `/dev/shm` ani `os.cpu_count()`;
5. zapisywać wartości limitów i `ray.cluster_resources()` w metadanych runa;
6. wykonać canary pamięci przed dużym eksperymentem.

W profilu z driverem poza pulą aktorów należy rozważyć reklamowanie Rayowi
`15` CPU i pozostawienie jednego CPU dla drivera, nadal w ramach przydziału
`--cpus-per-task=16`. Dokładny podział aktorów zostanie ustalony w małym canary.

## 11. Storage i limity plików

Migawka po utworzeniu venva:

| Przestrzeń | Użycie użytkownika | Limit | Pliki | Limit plików |
|---|---:|---:|---:|---:|
| HOME | około 1.177 GiB | 10 GiB | 48586 | 100000 |
| SCRATCH | około 2.9 MiB | 12 TiB | brak świeżej liczby | 1000000 |
| trwały storage `plggiobl` | około 11 KiB | 1 GiB | 1 | — |

Venv zajmuje około 889 MiB i około 46–47 tysięcy plików. HOME ma dużo miejsca
bajtowego, ale wykorzystuje już prawie połowę limitu inode. Nie tworzyć wielu
kopii venva i nie trzymać cache pakietów w HOME.

Preferowana struktura:

```text
$SCRATCH/islandsEA/
├── results/
├── logs/
│   └── slurm/
├── checkpoints/
└── tmp/
```

Scratch jest roboczy, nie jest backupem. Globalny filesystem miał 91% użycia.
Dane mogą być czyszczone automatycznie; finalne wyniki trzeba hashować,
archiwizować i pobierać do:

```text
C:\Users\piotr\UMISI\IslandsEA_summer\artifacts
```

## 12. Aktualna architektura CPU IslandsEA

Istotne pliki:

```text
hpc_benchmarks/run_benchmark.py
islands_desync/islands_desync/islands/core/IslandRunner.py
islands_desync/islands_desync/islands/core/Island.py
islands_desync/islands_desync/islands/core/Computation.py
islands_desync/islands_desync/islands/core/SignalActor.py
islands_desync/islands_desync/geneticAlgorithm/algorithm/genetic_island_algorithm.py
islands_desync/islands_desync/geneticAlgorithm/run_hpc/create_algorithm_hpc.py
islands_desync/islands_desync/geneticAlgorithm/run_hpc/benchmark_configuration.py
islands_desync/islands_desync/geneticAlgorithm/utils/benchmarks_refined/
```

Dla `N` wysp kod tworzy:

- `N` aktorów `Island`, każdy `num_cpus=1`;
- `N` aktorów `Computation`, każdy `num_cpus=1`;
- jeden `SignalActor`, `num_cpus=1`;
- driver wymaga jeszcze jednego fizycznego CPU poza pulą Ray.

Zapotrzebowanie:

```text
Ray CPU:       2*N + 1
fizyczne CPU:  2*N + 2
N=200:         401 Ray CPU, minimum 402 fizyczne CPU
```

Pilot Aresa rezerwuje 9 węzłów × 48 CPU = 432 CPU na każde powtórzenie.

`Computation` tworzy lokalny `genetic_island_algorithm`, który wykonuje
ewaluację przez jMetalPy/NumPy. Populacja ma 16 osobników, offspring 4, wymiar
200. Wywołania są małe i wykonywane per wyspa. W tej architekturze nie ma
zbiorczego bufora GPU ani aktora ewaluatora GPU.

## 13. Dlaczego nie wolno uruchomić profilu Aresa na Athenie

Na Athenie jedna zamówiona A100 daje proporcjonalnie 16 CPU. Utrzymanie
obecnego zapotrzebowania 402 CPU wymagałoby co najmniej:

```text
ceil(402 / 16) = 26 GPU
```

Jednorodny przydział wielowęzłowy mógłby skończyć się np. na 4 węzłach ×
7 GPU = 28 A100 i 448 CPU. GPU pozostawałyby niemal bezczynne, ponieważ
benchmarki nadal liczyłby NumPy na CPU.

To byłoby:

- kosztowne;
- nieefektywne;
- sprzeczne z przeznaczeniem Atheny dla zadań GPU;
- metodologicznie podejrzane, jeśli zmniejszono by rezerwacje aktorów bez
  zbadania wpływu na asynchroniczność migracji.

## 14. Docelowy kształt implementacji GPU

To jest projekt, nie stan obecnego kodu:

```text
200 logicznych wysp
        |
        v
kilka/kilkanaście CPU IslandShard actors
każdy przechowuje stan wielu wysp
        |
        v
batcher żądań ewaluacji
        |
        v
GpuEvaluator actor, num_gpus=1
        |
        v
wektorowy batch [B, 200] na A100
        |
        v
wyniki fitness kierowane do właściwych wysp
```

Najważniejsze założenia:

1. **Logiczna wyspa nie może być na stałe utożsamiana z dwoma pełnymi aktorami
   CPU.** Należy oddzielić stan eksperymentu od rezerwacji zasobów Ray.
2. **GPU nie powinno dostawać osobnego zdalnego wywołania dla każdego
   offspring batcha wielkości 4.** Readiness wykazał około 18-krotnie mniejszy
   throughput pełnego roundtripu przy `B=4`; żądania wielu wysp należy łączyć.
3. `GpuEvaluator` powinien być długowiecznym aktorem `num_gpus=1`, który raz
   ładuje stałe problemu, przesunięcia i macierze rotacji na kartę.
4. Każde żądanie musi zawierać co najmniej identyfikator wyspy, identyfikator
   kroku/generacji, indeks osobnika i dane rozwiązania. Odpowiedź musi być
   deterministycznie przypisana do nadawcy.
5. Migracje, seedy, liczba ewaluacji i warunek stopu pozostają per logiczna
   wyspa. Batchowanie nie może mieszać stanów generatorów losowych.
6. Na początku używać jednej A100, ponieważ taki jest zweryfikowany, tani profil
   `16 CPU + 125 GiB`. Dodawać GPU dopiero po stabilnym canary jednej karty;
   przewaga czasowa nad Aresem nie jest bramką.
7. Nie zmieniać semantyki historycznej kolejki migrantów bez osobnej decyzji
   metodologicznej i porównania wyników.

Możliwe miejsce interfejsu:

```python
class EvaluationBackend:
    def evaluate_batch(self, problem_id, vectors, context):
        """Zwraca fitness w tej samej kolejności co vectors."""
```

Backend CPU powinien pozostać implementacją referencyjną. Backend GPU musi
mieć identyczny kontrakt, jawny `dtype` oraz testy zgodności numerycznej.

## 15. Port 40 benchmarków

Warstwa **ewaluacji** została przeniesiona do jawnego API batchowego
NumPy/CuPy w `benchmarks_refined/batch.py` i `batch_kernels.py`. Definicje
skalarne, dane oraz operatory GA pozostają niezmienione. F1 z readiness
korzysta teraz z tego samego API. Szczegóły: `benchmarks_refined/BATCH.md`
i `athena_gpu/README.md`. Lokalnie przeszło 22016 porównań dla 170 instancji
oraz 1667 odrzuceń złych danych (Python 3.12.14, NumPy 2.3.5). Nowy backend
nie był jeszcze uruchamiany na A100; nie należy przenosić na niego statusu
historycznego readiness 3167902. Integracja z GA nadal pozostaje do wykonania.

Minimalny wspólny kontrakt:

```python
backend = NumpyBatchBackend()  # albo CupyBatchBackend() w aktorze GPU
backend.prepare(problem_id, dimension)
backend.evaluate_batch(problem_id, vectors, instance_seed=20260511)
# continuous input: [B, D], output: [B]
# binary input:     [B, number_of_bits], output: [B]
```

Wytyczne implementacyjne:

1. Zachować istniejące publiczne ewaluatory skalarne oraz ich walidację wejścia.
2. Dodać jawny backend batchowy NumPy oraz równoważny backend CuPy; nie
   przełączać globalnie `import numpy as np` na CuPy.
3. Dla 30 funkcji CEC zachować kolejność przesunięcia, skalowania, rotacji,
   shuffle, wag kompozycji i biasu. Stałe instancji należy skopiować na GPU raz
   w konstruktorze długowiecznego aktora, a nie przy każdej ewaluacji.
4. W środku batcha nie wykonywać `.get()`, `cp.asnumpy()` ani synchronizacji
   pomiędzy podfunkcjami. Jeden transfer wejścia i jeden transfer wyniku na
   cały batch.
5. Funkcje hybrydowe i kompozycyjne portować po funkcjach bazowych. F29/F30
   muszą korzystać z własnych danych instancji dokładnie jak CPU.
6. Dziesięć funkcji binarnych portować osobno. Zachować minimalizację, ujemne
   wyniki, semantykę `int64`, kolejność bitów NK i dokładne tabele instancji.
   LABS i NK nie mogą dostać przybliżonej lub losowanej implementacji GPU.
7. Continuous pozostaje `float64`. Zmiana na `float32` wymaga osobnej decyzji
   metodologicznej i nie może być domyślna.
8. Wyniki muszą wracać w tej samej kolejności co rekordy wejściowe. Do każdego
   rekordu batcha dołączać `run_id`, `island_id`, `step/evaluation` i lokalny
   indeks, aby nie pomylić odpowiedzi między wyspami.
9. Metadane mają pobierać `implementation_sha256()` z
   `benchmarks_refined.provenance`; readiness zapisał `null`, ponieważ odpytał
   bezpośrednio `CEC2014.metadata()`, które celowo nie dodaje hasha adaptera.
10. Nie zmieniać przy okazji migracji, acceptance, seedów, liczników ewaluacji,
    replacement ani formatu `research-v1-full-buffered`.

Każdy z 40 benchmarków musi mieć test:

- CPU scalar vs CPU batch;
- CPU scalar vs GPU batch dla optimum/golden inputs i deterministycznych
  losowych danych;
- kształtu, kolejności, braku mutacji wejścia i wartości skończonych;
- właściwych błędów dla złego wymiaru/dtype/zakresu;
- powtarzalności kolejnych wywołań i interleaved problem IDs;
- zgodności metadanych, data/definition hash i implementation hash.

Nie ma wymogu, aby każda funkcja GPU była szybsza od CPU. Wymagane jest jednak,
aby była rzeczywiście wykonywana na A100, nie wykonywała pętli Python per
osobnik, używała agregacji i nie zostawiała karty bez pracy przez konstrukcję
jednego remote call na cztery osobniki.

Kontrakt poprawności powinien sprawdzać:

- zgodność kształtów, identyfikatorów i kolejności wyników;
- wartości dla punktów referencyjnych;
- losowy zestaw deterministycznych wektorów;
- `float64` jako punkt odniesienia, chyba że jawnie zatwierdzono inny dtype;
- tolerancję absolutną i względną zapisaną w configu;
- brak mutacji wejścia;
- identyczne przesunięcia, rotacje i granice dziedziny;
- zgodność liczników ewaluacji per wyspa.

## 16. Metryki wymagane dla portu GPU

Oprócz istniejących metryk migracji i fitness zapisywać:

### Metadane środowiska

- model, UUID, compute capability i liczba GPU;
- sterownik, toolkit/runtime CUDA, backend i jego wersja;
- dtype;
- commit, dirty state, hash implementacji benchmarków;
- konto, partycja, job ID, node list, AllocTRES i ReqTRES;
- jawne limity CPU, object store i pamięci aplikacji.

### Metryki batchowania

- liczba requestów i batchy;
- rozkład wielkości batcha;
- czas oczekiwania w batcherze;
- czas host-to-device, kernela, synchronizacji i device-to-host;
- evaluations/s i batches/s;
- liczba wysp reprezentowana w batchu;
- liczba timeoutów, pustych batchy i błędów backendu.

### Metryki GPU

- GPU utilization;
- pamięć zajęta i maksimum;
- moc/energia, jeśli dostępna;
- czas bezczynności GPU;
- wykorzystanie per karta przy wielu GPU.

### Metryki naukowe

- zachować obecny `research-v1-full-buffered`;
- final fitness i fitness history per wyspa;
- pełne zdarzenia migracji;
- opóźnienia, kolejki i nierozpatrzeni migranci;
- rzeczywista liczba ewaluacji i kroków;
- porównanie CPU/GPU dla tych samych seedów.

## 17. Etapy wdrożenia i bramki

### Etap 0 — zakończony

- diagnostyka login i compute node;
- poprawny grant i scratch;
- venv;
- Ray widzi jedną A100;
- aktor GPU widzi `CUDA_VISIBLE_DEVICES=0`.

### Etap 1 — zakończony: backend

- wybrano `cupy-cuda117==10.6.0` z `CUDA/11.7.0`;
- instalacja binarnego wheela i `pip check` przeszły;
- `pip freeze` zapisano w artefaktach joba;
- prawdziwy kernel CuPy oraz synchronizacja przeszły na A100.

### Etap 2 — zakończony jako proof of concept: `r01_elliptic`

- publiczny scalar CPU był oracle;
- wektorowe CPU i GPU `float64` dały zgodne wyniki;
- wykonano pomiar `B=4..4096` przez prawdziwego aktora Ray;
- ograniczono pamięć Ray do 96 GiB + 8 GiB object store.

### Etap 2b — kod i testy CPU gotowe, walidacja GPU przygotowana

- wspólny kontrakt batch CPU/CuPy i wszystkie 30 continuous + 10 binary są zaimplementowane;
- testy, provenance i pomiary backendu są gotowe; lokalny NumPy przeszedł;
- `submit_validation.sh` jest przygotowany do walidacji A100, ale nie został zgłoszony;
- job sprawdzi także realistyczne `B=200,400,800,1200,1600,2400,3200` dla sześciu reprezentantów;
- dopiero potem podłączyć backend do IslandsEA.

### Etap 3 — mały canary IslandsEA

- kilka/kilkanaście logicznych wysp;
- jedna A100 i 16 CPU;
- twardy walltime;
- brak automatycznych retry;
- pełne metryki GPU i naukowe;
- jawne limity pamięci Ray.

### Etap 4 — canary 200 wysp

- nadal jedna A100, jeżeli jest w stanie obsłużyć batche;
- porównanie semantyki migracji z CPU;
- pomiar narzutu shardów i kolejki;
- dopiero na podstawie utilization decyzja o 2/4/8 GPU.

### Etap 5 — pilot trzy powtórzenia

- zamrożony config, commit, seedy i backend;
- canary gate;
- koszt maksymalny przed submittem;
- finalizer, walidacja i archiwum;
- ręczne pobranie ważnych wyników ze scratcha.

### Etap 6 — kampania 1800 runów

- dopiero po udanym pilocie;
- plan tablic job array i limit współbieżności;
- budżet GPUh z realnego pomiaru, nie z estymacji CPU;
- obserwowalność, brak nieograniczonych retry i twardy kill switch.

## 18. Wzorzec bezpiecznego joba Athena

Docelowy submitter powinien tworzyć katalog logów w scratch i przekazywać
ścieżki przez opcje `sbatch`, ponieważ dyrektywy `#SBATCH` nie rozwijają
zmiennych shellowych.

Minimalny profil jednej karty:

```text
account:       plgintobl-gpu-a100
partition:     plgrid-gpu-a100
nodes:         1
ntasks:        1
cpus-per-task: 16
mem:           128000M
gres:          gpu:1
time:          krótki, dobrany do etapu
```

W skrypcie joba:

```bash
set -euo pipefail
: "${SLURM_JOB_ID:?This script must run under SLURM}"
: "${ISLANDS_PROJECT_DIR:?Submitter must export repository path}"

module load Python/3.10.4
source "$HOME/venvs/islands-ray/bin/activate"

RAY_TMP_DIR="/tmp/r${SLURM_JOB_ID}"
[[ "$RAY_TMP_DIR" =~ ^/tmp/r[0-9]+$ ]] || exit 2
mkdir -p "$RAY_TMP_DIR"
```

`sbatch` kopiuje skrypt do `/var/spool/slurmd`. Skrypt batchowy nie może
wyznaczać repo przez katalog `BASH_SOURCE[0]`, bo otrzyma ścieżkę spool.
Submitter uruchomiony w repo ma wyliczyć absolutne `ISLANDS_PROJECT_DIR` i
przekazać je przez `--export`.

## 19. Historia diagnostyczna i koszt błędów

| Job | Wynik | Znaczenie |
|---|---|---|
| `3167364` | CANCELLED przed startem | pierwsza sonda, błędne konto; koszt 0 |
| `3167413` | COMPLETED, 7 s | wczesna sonda, raport pobrany za szybko |
| `3167422` | TIMEOUT, 1824 s | ręczna alokacja; potwierdziła A100 |
| `3167478` | TIMEOUT, 601 s | niewykorzystana ręczna alokacja |
| `3167494` | TIMEOUT, 613 s | test omyłkowo wykonany po powrocie na login |
| `3167517` | COMPLETED, 15 s | finalna automatyczna sonda Ray + A100 |
| `3167902` | COMPLETED, 28 s | CuPy F1, CPU/GPU match, pomiary i limity Ray |

Trzy ręczne timeouty zużyły około 0.844 GPUh. To niewielka wartość wobec
grantu, ale pokazuje, dlaczego kolejne testy mają być automatycznymi jobami
batch, a nie interaktywnym oczekiwaniem na prompt.

## 20. Pułapki, których nie wolno powtórzyć

1. Nie uruchamiać Ray na login node. Sygnały błędu: host `login01`, pusty
   `SLURM_JOB_ID`, brak `nvidia-smi`, zasoby Ray tylko CPU.
2. Nie czekać na task `num_gpus=1`, jeśli `ray.cluster_resources()` nie zawiera
   GPU; używać timeoutu i fail-fast.
3. Nie używać długiego `_temp_dir` Ray.
4. Nie zakładać, że `nvidia-smi CUDA Version` jest wersją toolkitu.
5. Nie zakładać, że GPU przydzielone aktorowi oznacza wykonanie kernela GPU.
6. Nie ufać pamięci hosta widocznej przez Ray/`free`; respektować alokację SLURM.
7. Nie używać `os.cpu_count()` jako liczby przydzielonych CPU.
8. Nie zapisywać logów, cache, wyników i checkpointów do repo lub HOME.
9. Nie tworzyć wielu venvów w HOME z powodu limitu 100000 plików.
10. Nie wykonywać automatycznych retry kosztownych jobów.
11. Nie uruchamiać kampanii bez canary, kosztu maksymalnego i kill switcha.
12. Nie wyznaczać katalogu repo z `BASH_SOURCE[0]` wewnątrz joba `sbatch`.

## 21. Co ma zrobić następna sesja Codexa

Kolejna sesja pracująca nad Atheną powinna:

1. przeczytać w całości `AGENTS.md`, `ATHENA_CONFIG.md`,
   `ATHENA_GPU_PORT_HANDOFF.md`, `ATHENA_INFO.md`, `athena_diagnostics_v4.txt`
   oraz `athena_kolejne_logi.txt`;
2. potwierdzić branch `summer_benchmarks_athena`;
3. nie uruchamiać obecnego pilota Aresa;
4. zachować zamrożony backend CuPy/CUDA i nie aktualizować go przy okazji;
5. wykorzystać działający `r01_elliptic` jako wzorzec, a nie osobny fork
   definicji benchmarków;
6. przeczytać gotowe `benchmarks_refined/BATCH.md` i `athena_gpu/README.md`, a następnie zwalidować wspólny backend na A100 przy pomocy `submit_validation.sh` (1 A100/16 CPU/15 min, maks. 0.25 GPUh, po akceptacji użytkownika);
7. zachować scalar CPU jako oracle poprawności;
8. zaprojektować `GpuEvaluator` i shardy logicznych wysp;
9. zachować zweryfikowane limity pamięci Ray i krótki katalog `/tmp/rJOBID`;
10. przygotować tani job canary z jedną A100;
11. zatrzymać się przed kosztownym submittem i przedstawić użytkownikowi
    maksymalny koszt oraz dokładny plan zasobów.

## 22. Warunek gotowości do pilota Athena

Pilot 200 wysp można uznać za gotowy dopiero, gdy wszystkie punkty są prawdziwe:

- [x] backend GPU jest przypięty wersją i działa w venvie;
- [x] co najmniej jeden benchmark wykonuje rzeczywisty kernel GPU;
- [x] F1 CPU/GPU correctness test przechodzi dla ustalonej tolerancji;
- [ ] wszystkie benchmarki wymagane przez pilot mają zwalidowany backend GPU;
- [ ] istnieje agregacja wywołań, która nie wysyła osobnego remote call per 4 offspring;
- [ ] 200 logicznych wysp nie wymaga 401 pełnych aktorów CPU;
- [ ] migracje i seedy zachowują uzgodnioną semantykę;
- [x] Ray ma zweryfikowane jawne limity pamięci dla profilu readiness;
- [ ] te same limity i rezerwacja CPU są zastosowane w launcherze IslandsEA;
- [ ] canary kończy się `COMPLETED 0:0`;
- [ ] GPU utilization oraz throughput są zapisane i sensowne;
- [ ] metadane pozwalają odtworzyć backend, config i mapping wysp;
- [ ] wszystkie duże artefakty trafiają na `$SCRATCH/islandsEA`;
- [ ] koszt maksymalny pilota został zaakceptowany przez użytkownika;
- [ ] nie ma automatycznych retry;
- [ ] finalizer waliduje komplet wyników przed oznaczeniem sukcesu.

Do czasu spełnienia tej checklisty Athena jest gotowa jako środowisko
deweloperskie i diagnostyczne, ale nie jako środowisko produkcyjnej kampanii
IslandsEA.
