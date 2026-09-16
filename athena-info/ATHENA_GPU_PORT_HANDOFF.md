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

# Handoff: port 40 benchmarków IslandsEA na GPU Atheny

Ostatnia aktualizacja: **2026-09-14**  
Odbiorca: sesja Codexa odpowiedzialna za implementację 40 benchmarków  
Klaster: **Athena / Cyfronet**  
Branch docelowy: **`summer_benchmarks_athena`**  
Stan: **backend batchowy 40 benchmarków zaimplementowany i sprawdzony na CPU; pełna walidacja CuPy na A100 oraz integracja z IslandsEA pozostają do wykonania**

Aktualizacja po porcie lokalnym: `islandsEA_student_fork/athena_gpu/README.md`
oraz `benchmarks_refined/BATCH.md` opisują gotowe API i przygotowany, jeszcze
niezgłoszony validation job. **Historyczny readiness 3167902 nie waliduje
nowego backendu.** Wyniki lokalne i dalsze kroki są podane w sekcji 17.

## 1. Decyzja projektowa

Athena ma zostać użyta, ponieważ zespół ma dostępny grant A100, podczas gdy
Ares jest chwilowo trudno dostępny. Port **nie musi udowodnić przewagi czasowej
nad Aresem**, aby być dopuszczony. Musi natomiast:

- wykonywać ewaluacje rzeczywiście na GPU;
- zachować definicje benchmarków i semantykę eksperymentu;
- działać w limicie jednej A100, 16 CPU i 125 GiB RAM;
- nie doprowadzać do OOM, zawieszonego Raya ani bezterminowych retry;
- agregować małe wywołania na tyle, aby karta nie była używana wyłącznie jako
  kosztowny zamiennik czteroelementowej funkcji CPU;
- zapisywać wyniki, logi i cache na `$SCRATCH`;
- pozostawić pełne metadane umożliwiające agregację 1800 runów.

Nie kopiować launchera Aresa i nie żądać 26–28 GPU tylko po to, aby uzyskać
402 CPU wymagane przez obecną architekturę aktorów.

## 2. Materiały, które trzeba przeczytać przed zmianami

1. `islandsEA_student_fork/AGENTS.md` — zasady projektu i obszary krytyczne.
2. `ATHENA_CONFIG.md` — aktualne źródło konfiguracji Atheny.
3. `ATHENA_INFO.md` — sprzęt, storage i historia diagnostyki.
4. `athena_diagnostics_v4.txt` — pełna sonda środowiska.
5. `athena_kolejne_logi.txt` — JSON i stdout readiness joba `3167902`.
6. `benchmarki_migracja.md` — zakres 40 benchmarków.
7. `jakie_metryki.md` — kontrakt metryk badawczych.

Przed edycją sprawdzić:

```bash
git branch --show-current
git status --short
```

Zmiany Athena mają pozostać na `summer_benchmarks_athena`. Nie wykonywać
commitów ani pushy za użytkownika bez jego jawnego polecenia.

## 3. Co zostało już zaimplementowane

Na branchu Athena znajduje się katalog `athena_gpu/`:

| Plik | Rola |
|---|---|
| `submit_readiness.sh` | bezpieczny submit 1×A100, logi/result na scratchu |
| `run_readiness.sh` | job SLURM, moduły, pin commita, CuPy bootstrap, cleanup |
| `gpu_readiness.py` | oracle CPU, F1 CuPy, Ray GPU actor, pomiary i JSON |
| `README.md` | instrukcje użycia i interpretacja markerów |

Dodatkowo utwardzono `athena_diagnostics/run_gpu_probe.sh`: wyjątek Raya nie
może już zostać zamieniony w fałszywy marker sukcesu, a zasoby pamięci są jawnie
ograniczane.

Readiness ma następujące zabezpieczenia:

- wyłącznie SLURM compute node, nigdy login node;
- dokładnie 1 GPU i 16 CPU;
- grant `plgintobl-gpu-a100`, partycja `plgrid-gpu-a100`;
- przypięty czysty commit i fail-closed po zmianie checkoutu;
- `max_restarts=0`, `max_task_retries=0`, brak automatycznego resubmitu;
- krótki i sprawdzony `RAY_TMP_DIR=/tmp/r${SLURM_JOB_ID}`;
- cleanup usuwa tylko ścieżkę pasującą do `^/tmp/r[0-9]+$`;
- `flock` chroni wspólny venv przed równoległą instalacją;
- odrzucenie mieszanej lub niespodziewanej dystrybucji CuPy;
- `pip check`, `pip freeze`, `nvidia-smi.csv` i atomowy `readiness.json`;
- jawne `OMP/BLAS/MKL/NUMEXPR_NUM_THREADS=1`;
- wszystkie trwałe artefakty na `$SCRATCH/islandsEA`.

## 4. Potwierdzony profil Atheny

```text
account:              plgintobl-gpu-a100
partition:            plgrid-gpu-a100
node profile:         1 node
GPU:                  1 × NVIDIA A100-SXM4-40GB
CPU allocation:       16
RAM allocation:       128000M = 125 GiB raportowane przez SLURM
Python module:         Python/3.10.4
CUDA module:           CUDA/11.7.0
venv:                  $HOME/venvs/islands-ray
Ray:                   2.9.3
NumPy:                 1.21.4
SciPy:                 1.7.3
CuPy distribution:     cupy-cuda117==10.6.0
CuPy:                  10.6.0
GPU CUDA runtime:      11070
driver:                595.71.05
Ray heap resource:     96 GiB
Ray object store:      8 GiB
Ray temp:              /tmp/r${SLURM_JOB_ID}
```

Nie aktualizować bibliotek „przy okazji”. Ten stary stack jest wymagany przez
projekt i został zweryfikowany razem. Zmiana CUDA/CuPy/Ray wymaga nowego,
oddzielnego readiness testu.

## 5. Wynik readiness joba `3167902`

```text
commit:       6bbdedf609e3e8eebd01fdea3b8be39d365a5d80
state:        COMPLETED
exit:         0:0
elapsed:      00:00:28
node:         t0020
AllocTRES:    billing=1,cpu=16,gres/gpu=1,mem=125G,node=1
cost:         około 0.0078 GPUh
result:       $SCRATCH/islandsEA/results/athena_gpu_readiness/3167902/readiness.json
stdout:       $SCRATCH/islandsEA/logs/slurm/athena-gpu-readiness-3167902.out
stderr:       $SCRATCH/islandsEA/logs/slurm/athena-gpu-readiness-3167902.err
```

Potwierdzone markery:

```text
ATHENA_CUPY_KERNEL_OK=1
ATHENA_R01_CPU_GPU_MATCH=1
ATHENA_RAY_MEMORY_LIMITS_OK=1
ATHENA_RAY_GPU_ACTOR_OK=1
ATHENA_GPU_READINESS_OK=1
```

Benchmark `r01_elliptic`, D=200, `float64`:

```text
data_sha256:       86ac55435ea9b3cb55d9df5129055aa63911fcd96791efd1fda189f3c39e0f89
validation batch:  32
rtol/atol:         1e-12 / 1e-6
max abs error:     6.103515625e-05
max relative err:  2.8385929965389834e-16
```

Duży błąd bezwzględny jest skutkiem skali funkcji; względna zgodność jest
bliska precyzji maszynowej. Nie luzować tolerancji bez analizy skali funkcji.

### Czasy pełnego roundtripu Ray

| B | CPU median | GPU/Ray median | CPU eval/s | GPU/Ray eval/s | GPU/CPU |
|---:|---:|---:|---:|---:|---:|
| 4 | 0.061 ms | 1.099 ms | 65 488 | 3 641 | 0.056× |
| 16 | 0.095 ms | 1.129 ms | 169 205 | 14 169 | 0.084× |
| 64 | 0.240 ms | 1.589 ms | 266 357 | 40 265 | 0.151× |
| 256 | 0.700 ms | 1.752 ms | 365 794 | 146 146 | 0.400× |
| 1024 | 2.253 ms | 2.612 ms | 454 488 | 392 102 | 0.863× |
| 4096 | 12.393 ms | 4.430 ms | 330 508 | 924 562 | 2.797× |

Dla B=4096 kernel osiągnął około 37.56 mln eval/s, lecz cała ścieżka Ray tylko
0.925 mln eval/s. Głównym kosztem jest zatem roundtrip, serializacja i transfer.
To nie dyskwalifikuje Atheny; wymusza wspólny batcher zamiast remote call dla
każdych czterech offspring.

## 6. Kanoniczny kod benchmarków

Nie tworzyć drugiego niezależnego zestawu definicji. Źródła CPU pozostają
źródłem prawdy:

```text
islands_desync/islands_desync/geneticAlgorithm/utils/benchmarks_refined/
├── adapters.py
├── cec2014.py
├── cec_functions.py
├── discrete.py
├── provenance.py
├── data/
└── tests/
```

Istniejące API skalarne i adaptery jMetalPy muszą pozostać kompatybilne.
Backend GPU należy dołożyć jako czystą warstwę batchową, a nie zastąpić scalar
API i nie przełączać całego modułu sztuczką `numpy -> cupy`.

Proponowany kontrakt:

```python
class EvaluationBackend:
    def evaluate_batch(self, problem_id, vectors, context=None):
        """Return one float64 objective per input row, preserving order."""
```

Kształty:

```text
continuous: input [B,D] float64, output [B] float64
binary:     input [B,N] bool/0-1, output [B] float64
```

Backendy:

- `NumpyBatchBackend` — referencja i fallback;
- `CupyBatchBackend` — wykonywany wyłącznie wewnątrz długowiecznego aktora
  `num_gpus=1`;
- scalar evaluator — ostateczny oracle poprawności, nie ścieżka produkcyjnego
  batchowania.

## 7. Wytyczne dla 30 continuous CEC

1. Zachować `float64`, granice `[-100,100]`, bias i kierunek minimalizacji.
2. Transformację skalarną `M @ (x-shift)` zapisać batchowo jako
   `(X-shift) @ M.T`.
3. Kernels z `cec_functions.py` rozszerzyć świadomie o oś batcha; redukcje mają
   działać po ostatniej osi, a nie po całej tablicy.
4. Shifts, matrices i shuffles załadować z istniejącego zweryfikowanego NPZ na
   CPU, sprawdzić hash, a następnie raz przenieść do pamięci aktora GPU.
5. Nie kopiować macierzy i shiftów przy każdym wywołaniu.
6. Hybrydy: najpierw rotacja całego wektora, potem shuffle, następnie grupy —
   dokładnie jak w CPU.
7. Kompozycje: zachować sigmy, divisors, numerator, sentinel `1e99`, warunek
   dokładnego zera i normalizację wag per rekord batcha.
8. F23 ma szczególny divisor `1e30` i komponent unrotated; nie upraszczać.
9. F29/F30 mają własne dane instancji i składają unbiased hybrids; nie używać
   danych F17–F22 z innej instancji.
10. Wewnątrz jednego batcha wykonać jeden H2D i jeden D2H. Zakazane są
    `cp.asnumpy()`, `.get()` i synchronizacje pomiędzy podfunkcjami.
11. Wersja CPU i GPU nie może mutować wejścia ani współdzielić zapisywalnych
    buforów między problemami.

Kolejność portu: funkcje bazowe → F1–F16 → hybrydy F17–F22 → kompozycje
F23–F28 → F29/F30. Działające F1 z readiness jest wzorcem transformacji i
walidacji, lecz należy je włączyć do wspólnego backendu.

## 8. Wytyczne dla 10 binary

Semantyka pozostaje minimizacyjna i obejmuje ujemne wyniki. Po walidacji
wejścia można konwertować do `int64`; nie wykonywać odejmowania na bool/uint.

- LABS: zachować ujemny merit factor i dokładne całkowite korelacje dla każdego
  laga. Pętla po strukturze/lugach jest dopuszczalna na pierwszym etapie, ale
  nie pętla Python po rekordach batcha.
- Trap4/Trap5/Royal Road: zachować wymagania podzielności i dokładne granice
  bloków.
- NK K=4: raz przenieść istniejące tabele wygenerowane przez
  `random.Random(20260511)`; zachować bieżący bit jako najbardziej znaczący i
  sąsiedztwo cykliczne.
- Leading Ones: zachować wartość długości pierwszego prefiksu jedynek.
- Alternating Bits: zachować wybór lepszego z dwóch naprzemiennych wzorców.
- MaxCut ring: zachować cykliczne przesunięcie i ujemny wynik.

Wyniki funkcji binarnych powinny być zgodne dokładnie (`rtol=0`, `atol=0`), z
wyjątkiem wartości naturalnie zmiennoprzecinkowych LABS/NK, dla których trzeba
udokumentować minimalną uzasadnioną tolerancję.

## 9. Macierz testów CPU/GPU

Każdy benchmark musi przejść:

1. scalar CPU vs NumPy batch;
2. scalar CPU vs CuPy batch;
3. optimum lub committed golden vector;
4. deterministyczne losowe batche o B=1,4,16,32;
5. przynajmniej jeden większy batch;
6. kolejne i przeplatane wywołania różnych problem IDs;
7. kształt `[B]`, kolejność, dtype, wartości finite i brak mutacji wejścia;
8. błędy dla niepoprawnego wymiaru, zakresu, bitów i dtype;
9. identyczne dane instancji oraz hash;
10. niepusty `implementation_sha256()` z `benchmarks_refined.provenance`.

Historyczny readiness 3167902 ma `implementation_sha256: null`, ponieważ wywoływał
bezpośrednio `CEC2014.metadata()`. To błąd metadanych testu, nie definicji F1;
obecny kod pobiera już hash z warstwy provenance backendu batchowego.

## 10. Integracja 200 logicznych wysp z jedną A100

Obecny kod rezerwuje `N Island + N Computation + SignalActor`, czyli dla
N=200 aż 401 logicznych CPU Ray oraz dodatkowy CPU drivera. Na jednej A100
Athena daje 16 CPU, więc ten model nie wystartuje.

Zalecany kierunek pierwszego canary:

```text
SLURM: 1 A100 + 16 CPU + 125 GiB
driver: 1 CPU poza pulą Ray
Ray:    maksymalnie 15 CPU + 1 GPU
GPU:    1 długowieczny GpuEvaluator actor (1 CPU, 1 GPU)
CPU:    kilka/kilkanaście IslandShard actors + coordinator/signal
state:  200 oddzielnych logicznych wysp wewnątrz shardów
```

Rozsądny punkt startowy to 8–13 shardów; dokładna liczba jest parametrem canary,
nie ustaleniem naukowym. Nie stosować setek aktorów `num_cpus=0` bez pomiaru —
każdy aktor nadal oznacza proces, pamięć i narzut schedulera.

Każda logiczna wyspa musi nadal mieć osobno:

- populację, RNG/seed, licznik ewaluacji i kroku;
- kolejkę imigrantów;
- topology neighbours;
- wybór emigrantów i acceptance;
- pełną telemetrię `research-v1-full-buffered`.

Shard ma kooperacyjnie przeplatać wyspy, nie łączyć ich populacji. Zmiana
fizycznego mapowania nie może zmienić tożsamości wyspy.

## 11. Batching i semantyka asynchroniczna

Dla ustawień pilota:

```text
islands=200
population=16
offspring=4
initial candidates=3200
steady-state candidates per ideal global wave=800
evaluations per island=8000
total evaluations per repeat=1,600,000
```

Readiness wskazuje, że osobny Ray roundtrip B=4 jest niedopuszczalnym wzorcem.
GpuEvaluator/batcher powinien agregować requesty wielu wysp, np. do targetu
`256–1024` z ograniczonym `max_wait_ms`. Dokładne wartości należy wybrać z
canary dla B=`200,400,800,1200,1600,2400,3200`.

Batcher musi zapisywać:

- request ID oraz `(run_id,island_id,step,evaluation,index)`;
- czas enqueue, dispatch i completion;
- liczbę requestów, rekordów i wysp w batchu;
- H2D, kernel, D2H, actor time oraz caller roundtrip;
- oczekiwanie na batch i powód dispatchu: size/timeout/flush;
- liczbę błędów, timeoutów i anulowanych rekordów.

Nie wolno bez dokumentacji zamienić algorytmu w globalnie synchroniczne
generacje. Oczekiwanie na batch wpływa na tempo logicznych wysp i może zmienić
badane opóźnienia migracji. Dlatego `max_wait_ms`, kolejność requestów i mapping
shardów są częścią metadanych eksperymentalnych.

## 12. Docelowy pilot po zakończeniu portu

Pierwszy właściwy pilot zachowuje ustalony profil badawczy:

```text
benchmark:             r01_elliptic
dimension:             200
islands:               200
topology:              torus 10 × 20 (jawny, metodologia-gated)
migrant selection:     best
migrant acceptance:    plain
migration interval:    5 (obecnie różnica licznika ewaluacji)
migrants:              5
population:            16
offspring:             4
stop:                  8000 evaluations per island
repeats:               3
metrics:               research-v1-full-buffered
effect horizon:        25 steps
```

Nie przechodzić od testów jednostkowych prosto do tego pilota. Kolejność:

1. statyczne/unit testy bez lokalnego compute;
2. GPU backend smoke dla wszystkich funkcji potrzebnych w danym canary;
3. mały IslandsEA canary, np. kilka wysp i 128/256 ewaluacji;
4. 200 wysp z małym budżetem ewaluacji;
5. jeden pełny repeat 8000;
6. dopiero trzy repeaty równolegle, każdy jako osobny job jednej A100;
7. kampania dopiero po walidacji finalizera i kosztu.

Każdy test GPU ma twardy walltime, brak automatycznego retry i koszt maksymalny
podany przed submittem. Dla 1 GPU i 15 minut maksimum wynosi `0.25 GPUh`.

## 13. Storage, logi i metadane

```text
$SCRATCH/islandsEA/
├── results/
├── logs/slurm/
├── checkpoints/
└── tmp/
```

Repo i venv pozostają w HOME. Wyniki, Ray logs, CuPy cache, pip cache,
checkpointy i SLURM stdout/stderr nie mogą trafiać do repo/HOME. Scratch nie
jest backupem; finalne archiwa należy pobierać do:

```text
C:\Users\piotr\UMISI\IslandsEA_summer\artifacts
```

`run_metadata.json` musi dodatkowo zawierać:

- `backend=athena-cupy`, dtype i wersję backendu;
- CUDA module/runtime, driver, model i UUID GPU;
- `SLURM_JOB_ID`, account, partition, node, ReqTRES/AllocTRES;
- Ray CPU/GPU/heap/object-store i `_temp_dir`;
- implementation/data/definition hashes;
- liczby shardów, mapping island→shard;
- target batch, max wait, pełny rozkład batchy;
- wszystkie parametry benchmarku, GA, migracji i topologii;
- seed policy i repeat;
- ścieżki storage oraz commit/dirty state.

## 14. Bramka sukcesu przed pilotem

- [x] SLURM przydziela właściwą A100 z właściwego grantu.
- [x] Ray widzi 16 CPU i 1 GPU.
- [x] Aktor `num_gpus=1` wykonuje prawdziwy kernel.
- [x] CuPy/CUDA są przypięte i `pip check` przechodzi.
- [x] F1 D=200 CPU/GPU match przechodzi.
- [x] Ray respektuje cap 96 GiB + 8 GiB w readiness.
- [x] Wspólny batch API obejmuje wszystkie 40 benchmarków, z zachowaniem scalar API.
- [x] Macierz NumPy batch vs scalar/C oraz provenance przechodzi lokalnie.
- [ ] Pełna macierz 40 benchmarków CPU/GPU z provenance przechodzi na docelowej A100.
- [ ] IslandsEA korzysta z backendu GPU zamiast scalar CPU.
- [ ] 200 logical islands mieści się w 15 CPU Ray bez zakleszczenia.
- [ ] Batcher zachowuje identyfikatory i mierzy własny wpływ na asynchroniczność.
- [ ] Metryki migracji pozostają kompletne i walidator je akceptuje.
- [ ] Canary 200 wysp z małym budżetem kończy się sukcesem.
- [ ] Jeden pełny repeat przechodzi przed równoległymi trzema.
- [ ] Finalizer odróżnia `COMPLETED` SLURM od kompletnego wyniku naukowego.
- [ ] Użytkownik zatwierdził maksymalny koszt kolejnego etapu.

## 15. Czego nie robić

- Nie uruchamiać obliczeń na login node.
- Nie używać długiej ścieżki Ray pod HOME/SCRATCH.
- Nie ufać `os.cpu_count()`, `free` ani całemu `/dev/shm` hosta.
- Nie wysyłać taska GPU, gdy `cluster_resources()` nie zawiera GPU.
- Nie wykonywać jednego remote call na cztery offspring.
- Nie tworzyć 401 aktorów CPU na alokacji 16 CPU.
- Nie zmieniać operatorów, migracji, acceptance ani seedów przy porcie funkcji.
- Nie używać `float32` bez jawnej decyzji metodologicznej.
- Nie regenerować danych CEC ani tabel NK.
- Nie traktować `nvidia-smi CUDA Version` jako wersji toolkitu.
- Nie dodawać automatycznych retry kosztownych jobów.
- Nie rozpoczynać 1800 runów bez canary, finalizera i kill switcha.

## 16. Uzgodniony zakres sesji benchmarkowej (wykonany lokalnie)

1. Potwierdzić branch i czysty working tree.
2. Zaprojektować wspólny `evaluate_batch` bez zmiany scalar API.
3. Przenieść działające F1 z readiness do wspólnej warstwy CPU/CuPy.
4. Naprawić zapis `implementation_sha256` w metadanych GPU.
5. Dodać automatyczne testy F1 oraz kilku reprezentantów: funkcja bazowa bez
   rotacji, hybryda, kompozycja, LABS i NK.
6. Rozszerzyć port na pozostałe 40 po przejściu reprezentatywnych przypadków.
7. Przygotować krótki, automatyczny 1-A100 validation job; nie submitować go
   samodzielnie bez akceptacji użytkownika.
8. Zatrzymać się przed przebudową aktorów IslandsEA i przed produkcyjnym
   pilotem, przedstawiając diff, testy i maksymalny koszt następnego joba.

## 17. Wynik portu lokalnego — 2026-09-14

- `benchmarks_refined/batch.py`: jawne backendy NumPy/CuPy, przygotowanie i
  cache stałych instancji, walidacja wejścia, uporządkowany wynik hosta `[B]`,
  limit B=8192, float64, pojedyncze H2D/D2H dla kandydatów/wyniku.
- `batch_kernels.py`: te same 14 bazowych wzorów z osią batcha; parametry,
  dane CEC i tabele NK pochodzą z kanonicznego pakietu. Nie zmieniono
  `cec2014.py`, `cec_functions.py`, `discrete.py`, adapterów ani danych.
- `batch_validation.py`, `tests/test_batch.py`: wszystkie 30 × D=10/30/50/100/200
  oraz 10 × N=60/200; 2220 referencji C, optima, losowe i brzegowe wejścia,
  dtype, kolejność, brak mutacji, RNG, hashe i odrzucanie błędnych danych.
- Lokalnie przeszło 12 starych testów wzorów + 4 nowe batchowe; 1 test CuPy
  został jawnie pominięty. Macierz liczy 170 instancji, 22016 porównań i
  1667 odrzuconych błędnych wejść. Raport: `athena_gpu/validation_cpu.json`,
  Python 3.12.14 / NumPy 2.3.5. To nie jest certyfikacja stosu Atheny.
- Trzy testy submittera z atrapami git/sbatch przeszły; sprawdzono składnię
  Bash i Python 3.10. Testy nie kontaktują się z HPC.
- `gpu_readiness.py` korzysta ze wspólnego F1 i zapisuje hash implementacji.
  Schema 2 zmienia definicję niektórych pomiarów — szczegóły w README.
- `gpu_validation.py` i `submit_validation.sh` są przygotowane do testu
  wszystkich 40 funkcji wewnątrz rzeczywistego aktora A100, z porównaniem
  scalar/NumPy/C oraz pomiarami 6 reprezentantów dla B=200..3200.
- Wspólny wrapper trzyma cache na scratchu, sprawdza rzeczywiste ścieżki
  wyników/logów i kończy wyłącznie grupę procesów swojego joba. Logi Raya
  są zachowywane po obsłużonym błędzie; nie ma `ray stop --force` na hosta.

**Nie wykonano:** commita, pusha, submitu GPU, pełnej walidacji CuPy,
przebudowy aktorów, batchera requestów ani pilota. Ścieżka GA jest nadal CPU.

Najbliższy etap po przeniesieniu czystego commita przez użytkownika:
`bash athena_gpu/submit_validation.sh`, z jego akceptacją kosztu;
**1 A100, 16 CPU, 125 GiB, 15 min, maks. 0.25 GPUh**. Wewnątrz 15 CPU Ray
oraz 1 CPU drivera i cap 96/8 GiB. Sukces wymaga `COMPLETED 0:0`, JSON `passed`,
40 funkcji/170 instancji i trzech markerów `ATHENA_40_*` z README.
Po tym teście można osobno projektować shardy/batcher; nie wykonywać
automatycznie następnych etapów kampanii.
