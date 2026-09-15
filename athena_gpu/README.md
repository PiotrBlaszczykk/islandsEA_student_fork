> Aktualizacja 2026-09-15: obowiązuje **144 wyspy**, torus **12×12**,
> complete oraz wybrane **ER4 / WS3 / BA**. Źródło aktualnych ustawień i status
> załączników: [STUDY_144.md](../STUDY_144.md). ER4 dostarczono jako 150 węzłów;
> jego uruchomienie przy 144 jest zablokowane do rozstrzygnięcia. Historyczne
> pomiary sprzętu pozostają niezmienione; D=200 oznacza wymiar benchmarku.

# Athena: walidacja 40 benchmarków na GPU

Stan 2026-09-14: `benchmarks_refined/batch.py` i `batch_kernels.py` implementują
30 CEC2014 oraz 10 funkcji binarnych jako batche NumPy/CuPy. Instrukcja API,
matematyka, tolerancje i pomiary są w [BATCH.md](../islands_desync/islands_desync/geneticAlgorithm/utils/benchmarks_refined/BATCH.md).
Wzory skalarne, dane i adaptery jMetalPy pozostają bez zmian. Główny IslandsEA
nadal wykonuje ewaluację CPU; shardy wysp i agregator requestów są kolejnym etapem.

**Lokalna walidacja przeszła; nowego backendu nie uruchamiano jeszcze na A100.**
[validation_cpu.json](validation_cpu.json) zapisuje Python 3.12.14,
NumPy 2.3.5, 170 instancji, 22016 porównań i 1667 odrzuconych błędnych wejść.
Przeszło 12 dotychczasowych testów wzorów i 4 nowe testy batchowe; jeden test
CuPy został jawnie pominięty z powodu braku uruchomienia na GPU. Trzy testy
submittera przeszły z atrapami `git`/`sbatch`, bez kontaktu z klastrem.
Syntax Python 3.10 i Bash sprawdzono lokalnie. To nie zastępuje walidacji
NumPy 1.21.4 / CuPy 10.6.0 na docelowym sprzęcie.

## Następny krok: jeden validation job dla całej czterdziestki

Przygotowane, **niezgłoszone** uruchomienie. Po commit/push/pull użytkownika
na czystym branchu `summer_benchmarks_athena`, z login node Atheny:

```bash
cd "$HOME/islandsEA_student_fork"
bash athena_gpu/submit_validation.sh
```

To jedno zadanie, bez wysp ani GA: **1 A100, 16 CPU, 128000M, 15 minut,
maksymalnie 0.25 GPUh**, konto `plgintobl-gpu-a100`, partycja `plgrid-gpu-a100`.
Nie ma automatycznego retry, restartu aktora ani resubmitu. Ray otrzymuje
15 CPU (1 zostaje dla drivera), 1 GPU, 96 GiB heap i 8 GiB object store.
Wewnątrz działa jeden aktor `num_cpus=1,num_gpus=1` z rzeczywistym CuPy.

`gpu_validation.py` sprawdza czysty przypięty commit przed i po obliczeniach,
Python 3.10, Ray 2.9.3, NumPy 1.21.4, SciPy 1.7.3, jMetalPy 1.5.5,
CuPy 10.6.0, runtime CUDA 11.7 oraz model A100. Wykonuje wspólną macierz
wszystkich 40 funkcji (w tym wszystkie wymiary CEC i projektowe 200D).
Potem mierzy F1, F6, F22, F30, LABS i NK przy D/N=200 oraz
B=144/288/576/864/1152/1728/2304, z warmupem i trzema próbkami na rozmiar.
Raport rozdziela lokalny CPU batch, kernel GPU, transfery, aktora i Ray
roundtrip; nie obiecuje przyspieszenia każdej funkcji.

Wyniki:

```text
$SCRATCH/islandsEA/results/athena_benchmark_validation/<JOB_ID>/validation.json
$SCRATCH/islandsEA/results/athena_benchmark_validation/<JOB_ID>/pip-freeze.txt
$SCRATCH/islandsEA/results/athena_benchmark_validation/<JOB_ID>/nvidia-smi.csv
$SCRATCH/islandsEA/logs/slurm/athena-gpu-readiness-<JOB_ID>.out
$SCRATCH/islandsEA/logs/slurm/athena-gpu-readiness-<JOB_ID>.err
```

Prefix logów `athena-gpu-readiness` jest wspólny dla obu trybów; submitter
wypisuje `ATHENA_VALIDATION_MODE=suite` i dokładne ścieżki. CuPy/pip/XDG cache
i pliki tymczasowe trafiają do katalogu wyniku na scratchu. Ray używa krótkiego
`/tmp/r<JOB_ID>` dla socketów. Po błędzie jego logi są kopiowane do
`ray-failure-logs` w katalogu wyniku; cleanup dotyczy grupy procesów tego joba,
bez hostowego `ray stop --force`. Brutalne zakończenie/OOM może uniemożliwić
zapis JSON/cleanup — sam `COMPLETED` nigdy nie jest dowodem poprawności.

Sukces wymaga `COMPLETED 0:0`, `validation.json` ze statusem `passed`,
`validation.benchmark_count=40`, `instance_count=170` i markerów:

```text
ATHENA_40_CPU_GPU_MATCH=1
ATHENA_40_GPU_VALIDATION_OK=1
ATHENA_40_GPU_VALIDATION_JOB_OK=1
```

Po niezgodności wyników lub timeoutcie najpierw sprawdzić JSON i logi.
Nie luzować tolerancji ani nie przechodzić do pilota. Po sukcesie tego joba
nadal pozostają integracja GPU z logicznymi wyspami, batcher i osobny canary GA.

Lokalne testy submittera (z atrapami, bez SLURM):

```bash
python -m unittest discover -s athena_gpu/tests -v
```

## Zachowany canary F1

`submit_readiness.sh` nadal uruchamia wyłącznie F1. Teraz korzysta z tego
samego backendu co pozostałe funkcje i zapisuje niepusty hash implementacji.
Schema `readiness.json` wzrosła do 2: czas CPU obejmuje walidację wejścia,
a H2D jest mierzony zdarzeniami CUDA. Tych składowych nie porównywać wprost
z dawnym hostowym czasem submitu w jobie 3167902. Tamten job potwierdził
poprzednią implementację F1, nie wszystkie nowe funkcje.

Ten katalog przygotowuje jeden tani, automatyczny test przed portem IslandsEA
na GPU. Nie uruchamia 144 wysp ani właściwego pilota.

Canary sprawdza:

- przypięty backend `cupy-cuda117==10.6.0` z modułem `CUDA/11.7.0`;
- prawdziwe obliczenie `r01_elliptic` na A100 w `float64`;
- zgodność wyniku CPU/GPU dla danych CEC2014 D=200;
- przepustowość batchy 4, 16, 64, 256, 1024 i 4096;
- wykonanie przez aktora Ray `num_gpus=1`;
- jawne limity Ray: 16 CPU, 96 GiB pamięci logicznej i 8 GiB object store;
- zapis wyniku i logów wyłącznie pod `$SCRATCH/islandsEA`.

CuPy jest instalowane tylko wtedy, gdy nie ma jeszcze dokładnie właściwej
dystrybucji. Instalacja odbywa się wewnątrz alokacji SLURM i modyfikuje
istniejący venv Atheny `$HOME/venvs/islands-ray`. Skrypt odmawia działania,
jeżeli wykryje inną dystrybucję lub wersję CuPy, aby nie mieszać pakietów.

## Uruchomienie

Po commit/push/pull wykonanym przez użytkownika, na login node Atheny:

```bash
cd "$HOME/islandsEA_student_fork"
git status --short --branch
bash athena_gpu/submit_readiness.sh
```

Profil joba:

```text
account:       plgintobl-gpu-a100
partition:     plgrid-gpu-a100
GPU:           1 × A100
CPU:           16
RAM:           128000M
walltime:      00:15:00
max cost:      0.25 GPUh
automatic retry: disabled
```

Skrypt wypisuje `ATHENA_GPU_READINESS_JOB_ID`. Monitorowanie:

```bash
squeue -j JOB_ID -o "%.18i %.20P %.24j %.10T %.10M %.10l %R"
sacct -j JOB_ID -P \
  --format=JobIDRaw,JobName,Account,State,ExitCode,Elapsed,AllocCPUS,AllocTRES,NodeList
```

Logi:

```text
$SCRATCH/islandsEA/logs/slurm/athena-gpu-readiness-<JOB_ID>.out
$SCRATCH/islandsEA/logs/slurm/athena-gpu-readiness-<JOB_ID>.err
```

Wynik:

```text
$SCRATCH/islandsEA/results/athena_gpu_readiness/<JOB_ID>/readiness.json
$SCRATCH/islandsEA/results/athena_gpu_readiness/<JOB_ID>/pip-freeze.txt
$SCRATCH/islandsEA/results/athena_gpu_readiness/<JOB_ID>/nvidia-smi.csv
```

Warunek sukcesu to `COMPLETED 0:0`, JSON ze statusem `ok` i wszystkie markery:

```text
ATHENA_CUPY_KERNEL_OK=1
ATHENA_R01_CPU_GPU_MATCH=1
ATHENA_RAY_MEMORY_LIMITS_OK=1
ATHENA_RAY_GPU_ACTOR_OK=1
ATHENA_GPU_READINESS_OK=1
```

Nie ponawiać automatycznie nieudanego joba. Najpierw sprawdzić JSON oraz oba
logi SLURM.
