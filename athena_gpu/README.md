# Athena GPU readiness canary

Ten katalog przygotowuje jeden tani, automatyczny test przed portem IslandsEA
na GPU. Nie uruchamia 200 wysp ani właściwego pilota.

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
