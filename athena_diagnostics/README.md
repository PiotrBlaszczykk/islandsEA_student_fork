# Diagnostyka Atheny przed portem uruchomień

Ten katalog nie uruchamia benchmarku IslandsEA. Zbiera informacje potrzebne do
osobnego zaprojektowania profilu Atheny: scheduler, grant, storage, CPU/NUMA,
GPU, sterownik/CUDA, sieć, środowisko Pythona oraz widoczność GPU w Ray.

Oficjalny profil Atheny to partycja `plgrid-gpu-a100`: 128 rdzeni CPU, 1024 GB
RAM i 8× NVIDIA A100-SXM4-40GB na węzeł. Przydział jednej karty odpowiada 16 CPU
i 128000 MB RAM. Konto musi mieć sufiks `-gpu-a100`.

## Uruchomienie

Po commit/push/pull wykonanym przez użytkownika, na login node Atheny:

```bash
cd "$HOME/islandsEA_student_fork"
bash athena_diagnostics/collect_athena_info.sh
```

Domyślnie skrypt zapisuje mały raport w:

```text
$HOME/artifacts/athena_duagnostics.txt
```

Następnie zgłasza w stanie `HOLD`, opisuje w raporcie i zwalnia minimalny job:

- partycja `plgrid-gpu-a100`,
- konto `plgintobl-gpu-a100`,
- 1 GPU A100, 16 CPU, 128000 MB RAM,
- limit 10 minut, czyli maksymalnie 1/6 GPUh,
- bez właściwego benchmarku i bez instalowania pakietów.

Jeżeli nazwa grantu jest inna, ustaw ją przed uruchomieniem:

```bash
ATHENA_ACCOUNT=NAZWA-GRANTU-gpu-a100 \
  bash athena_diagnostics/collect_athena_info.sh
```

Pozostałe parametry można nadpisać przez `ATHENA_PARTITION`, `ATHENA_GRES`,
`ATHENA_CPUS_PER_TASK`, `ATHENA_MEMORY` i `ATHENA_PROBE_TIME`. Diagnostyka tylko
z login node, bez zużycia GPU:

```bash
bash athena_diagnostics/collect_athena_info.sh --login-only
```

Skrypt wypisze `ATHENA_GPU_PROBE_JOB_ID`. Monitorowanie:

```bash
squeue -j JOB_ID
sacct -j JOB_ID \
  --format=JobID,State,ExitCode,Elapsed,AllocCPUS,AllocTRES,ReqTRES,NodeList
grep ATHENA_GPU_PROBE_COMPLETE "$HOME/artifacts/athena_duagnostics.txt"
```

Raport jest kompletny dopiero po obecności:

```text
ATHENA_RAY_GPU_OK=1
ATHENA_GPU_PROBE_COMPLETE=1
```

Od wersji po diagnostyce `3167517` wyjątek Ray, brak A100 albo nieskuteczne
limity pamięci kończą sondę niezerowym kodem. Samo dopisanie raportu nie może
już dać fałszywego sukcesu.

Logi techniczne joba trafiają domyślnie pod
`$SCRATCH/islandsEA/logs/slurm/`, a nie do repozytorium.

## Pobranie na laptop

Po zakończeniu joba, w PowerShellu:

```powershell
cd C:\Users\piotr\UMISI\IslandsEA_summer\main_codebase\islandsEA_student_fork
.\athena_diagnostics\download_report.ps1
```

Powstanie dokładnie:

```text
C:\Users\piotr\UMISI\IslandsEA_summer\main_codebase\athena_diagnostics.txt
```

## Ważne przed właściwym portem

Obecna implementacja IslandsEA jest obciążeniem CPU (Ray + jMetalPy/NumPy).
Samo przydzielenie A100 nie przyspieszy jej i nie spełnia wymogu używania Atheny
wyłącznie do zadań GPU. Najpierw raport musi potwierdzić dostępny stos CUDA/Ray;
dopiero potem należy zdecydować, która część ewaluacji rzeczywiście zostanie
przeniesiona na GPU i jak mapować wyspy na karty. Nie uruchamiaj na Athenie
istniejącego profilu Aresa 9×48 CPU.

Źródła:

- https://docs.hpc.cyfronet.pl/supercomputers/athena/
- https://docs.hpc.cyfronet.pl/environment/batch-system/accounts-and-grants/
