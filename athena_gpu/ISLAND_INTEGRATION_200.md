# Athena GPU: projekt integracji 200 logicznych wysp

Stan projektu: 2026-09-16. Ten dokument opisuje następny etap techniczny po
walidacji backendu CuPy. Nie jest launcherem, nie zgłasza jobów i nie zatwierdza
200 wysp do aktualnej macierzy badawczej.

## 1. Zakres i status metodologiczny

Aktualne badanie opisane w `STUDY_144.md` wymaga 144 wysp. Profil opisany tutaj
ma dokładnie 200 logicznych wysp, ponieważ został jawnie zlecony jako projekt
integracyjny Atheny. Musi być oznaczany w metadanych jako
`athena-integration-200`, nigdy `approved-144`, i jego wyników nie wolno mieszać
z macierzą 144 bez osobnej decyzji metodologicznej.

Docelowy entrypoint pełnego profilu musi wymagać jednocześnie dokładnie 200
wysp i jawnej flagi `--confirm-athena-integration-200`. Mniejsze canary używają
osobnego `--diagnostic`; żaden z tych trybów nie przechodzi przez study launcher
Aresa ani nie osłabia jego walidacji 144.

Projekt zachowuje:

- osobny stan, populację, RNG, seed, krok i licznik ewaluacji każdej wyspy;
- 8000 ewaluacji na wyspę, populację 16 i offspring 4;
- migrację mierzoną różnicą liczników ewaluacji, interwał 5 i grupę 5;
- wybór migrantów, acceptance, kolejność sąsiadów i dokładny graf;
- pełny profil `research-v1-full-buffered`, w tym signed delays, kolejki,
  acceptance, survival, fitness i runtime;
- `float64`, kanoniczne dane problemów i formułę seedów
  `repeat_base + island_id`.

Zmienia się wyłącznie fizyczne rozmieszczenie pracy i sposób agregowania
ewaluacji. Asynchroniczne trajektorie nie muszą być bitowo identyczne z CPU,
ale żadna populacja, kolejka migracji ani strumień RNG nie może zostać scalony
z inną logiczną wyspą.

## 2. Dowód wejściowy: job 3168014

Pełna walidacja backendu zakończyła się:

```text
job:       3168014
state:     COMPLETED
exit:      0:0
elapsed:   47 s
node:      t0029
resources: 1 A100, 16 CPU, 125 GiB
batch MaxRSS: 3,874,528 KiB
commit:    d9795315f28d06945ab9af46e9cc54e9c8bb8a39
```

Powstał `validation.json` o rozmiarze około 736 KiB, a stdout zawiera wszystkie
markery:

```text
ATHENA_40_CPU_GPU_MATCH=1
ATHENA_40_GPU_VALIDATION_OK=1
ATHENA_40_GPU_VALIDATION_JOB_OK=1
```

Skrypt wypisuje te markery dopiero po przejściu macierzy 40 benchmarków / 170
instancji. Odczyt JSON potwierdził `status=passed`, 22 016 sprawdzonych wierszy,
`global_rng_unchanged=true` i 42 rekordy timingów. Błąd
`libpython3.10.so.1.0` widziany
później pochodził z próby odczytu JSON-a na login node bez załadowania modułu
`Python/3.10.4`; nie pochodził z joba.

Od zwalidowanego commita do lokalnego commita bazowego `dbe27de...` (HEAD
w czasie analizy) nie zmieniły się
`batch.py`, `batch_kernels.py`, dane ani wzory. Zmieniły się rozmiary pomiarowe
w `gpu_validation.py` z 200/400/800/1200/1600/2400/3200 na wielokrotności 144,
dokumentacja i test konfiguracji badania. Job jest zatem dowodem dla bieżącej
implementacji backendu, natomiast dokładne mediany z jego JSON-a należy jeszcze
dołączyć do decyzji o finalnej polityce batchera.

Reprezentatywne wyniki pełnego Ray roundtripu (speedup względem lokalnego
NumPy batch na tym samym węźle):

| Funkcja | Pierwsze B ze speedup > 1 | GPU roundtrip B=800 | Speedup B=800 | Speedup B=3200 |
|---|---:|---:|---:|---:|
| `r01_elliptic` | 2400 | 2.924 ms | 0.666x | 1.649x |
| `r06_weierstrass` | 200 | 2.810 ms | 47.658x | 99.368x |
| `r22_hybrid6` | 400 | 6.189 ms | 1.849x | 6.754x |
| `r30_composition8` | 400 | 8.402 ms | 2.856x | 9.036x |
| `b01_labs_binary` | 400 | 13.055 ms | 2.473x | 7.505x |
| `b03_nk_k4` | 2400 | 3.302 ms | 0.583x | 1.626x |

Wniosek: większe batche są korzystne, ale 200 wysp z offspring 4 może mieć
maksymalnie 800 niezależnych kandydatów w locie bez spekulacji lub zmiany GA.
Nie czekamy więc w krokach na nieosiągalne 2400/3200 tylko po to, aby poprawić
speedup F1/NK. Inicjalizacja jest osobną fazą z naturalnym B=3200 przed startem
pomiaru migracji i może użyć większego targetu.

## 3. Budżet jednej A100 i 16 CPU

SLURM przydziela 16 fizycznych CPU. Jeden pozostaje dla drivera, a Ray reklamuje
15 CPU i jedną GPU, z potwierdzonymi limitami 96 GiB heap oraz 8 GiB object
store.

| Składnik | Liczba | CPU/aktor | GPU/aktor | Razem CPU |
|---|---:|---:|---:|---:|
| `GpuEvaluator` | 1 | 1 | 1 | 1 |
| `EvaluationBatcher` | 1 | 1 | 0 | 1 |
| `MigrationRouter` | 1 | 1 | 0 | 1 |
| `IslandShard` | 12 | 1 | 0 | 12 |
| Ray razem | 15 |  |  | 15 |
| driver poza pulą Ray | 1 |  |  | 1 |

Nie tworzymy `200 Island + 200 Computation + SignalActor`. Dwanaście shardów
otrzymuje deterministyczny, zbalansowany przydział: pierwsze osiem shardów po
17 wysp, pozostałe cztery po 16 (`8*17 + 4*16 = 200`). Mapping jest zapisywany
w metadanych i nie zmienia się w trakcie runa.

## 4. Graf wykonania

```text
driver (1 fizyczny CPU, poza Ray)
  |-- tworzy i waliduje dokładną topologię oraz mapping wyspa -> shard
  |-- uruchamia 12 IslandShard równolegle
  |-- czeka na wyniki i waliduje komplet artefaktów
  |
  +--> IslandShard[0..11] -- pojedyncze requesty logicznych wysp --+
  |                                                              |
  |                                                   EvaluationBatcher
  |                                                              |
  |                                          zagregowany [B,D], B <= limit
  |                                                              |
  |                                                GpuEvaluator (1 A100)
  |
  +--> MigrationRouter <-- send/drain/ack per logiczna wyspa -----+
```

Driver nie wykonuje obliczeń GA. `GpuEvaluator` jest jedynym właścicielem CuPy
i CUDA. `EvaluationBatcher` nie importuje CuPy. `MigrationRouter` nie wykonuje
ewaluacji ani nie przechowuje populacji.

Tworzenie aktorów jest dwuetapowe, ponieważ obecny builder tylko dla wyspy 0
zakłada wspólny katalog runa. Driver najpierw tworzy stan wyspy 0 w jej shardzie
i czeka na potwierdzenie utworzenia katalogu oraz manifestu. Dopiero potem
zezwala wszystkim shardom utworzyć pozostałe algorytmy. Usuwa to wyścig bez
dodawania opóźnienia do mierzonej części eksperymentu.

## 5. Maszyna stanów logicznej wyspy

Każdy `IslandShard` przechowuje dla każdej przypisanej wyspy strukturę:

```text
island_id
algorithm
python_random_state
numpy_random_state
evaluation_phase: initial | offspring
pending_solutions
pending_request_id
logical_step / logical_evaluations
migration adapter and buffered telemetry
runtime timestamps
```

Shard działa kooperacyjnie:

1. Odtwarza RNG konkretnej wyspy.
2. Przygotowuje populację początkową albo offspring bez ewaluacji.
3. Zachowuje jej RNG i wysyła nieblokujący request do batchera.
4. Utrzymuje najwyżej jeden request w locie na logiczną wyspę.
5. `ray.wait()` odbiera pierwszy gotowy request, nie czeka na pełną falę.
6. Przypisuje wyniki dokładnie do tych samych obiektów solution i kończy krok.
7. Natychmiast przechodzi do kolejnego kroku tej wyspy, jeśli warunek stopu
   jeszcze nie zaszedł.

Nie istnieje bariera generacji obejmująca 200 wysp. Batcher może naturalnie
zwrócić wiele requestów naraz, ale shard rozpatruje je jako osobne zakończenia,
a timeout batchera pozwala wypuścić częściowy batch bez oczekiwania na wszystkie
wyspy.

## 6. Zachowanie seedów i RNG

Dotychczas osobny proces aktora pozwalał wywołać:

```text
random.seed(repeat_base + island_id)
numpy.random.seed((repeat_base + island_id) mod 2^32)
```

W shardzie globalne moduły `random` i `numpy.random` są wspólne dla wielu
algorytmów. Każde wejście do kodu danej wyspy musi więc wykonać transakcję:

```text
save shard globals
restore island Python/NumPy RNG states
execute one deterministic logical phase
capture island Python/NumPy RNG states
restore shard globals
```

Shard jest jednowątkowy; nie wolno wykonywać dwóch takich transakcji
równocześnie. Batcher, router i GPU nie mogą korzystać z RNG algorytmu. Losowy
wybór celu migracji odbywa się wewnątrz transakcji źródłowej wyspy, na tej samej
uporządkowanej liście sąsiadów, więc zużywa jej własny strumień tak jak obecnie.

Test obowiązkowy: dwa przeplecenia tych samych wysp muszą dać każdej wyspie
ten sam prywatny ciąg Python/NumPy co uruchomienie jej w izolacji.

## 7. Rozdzielenie kroku GA wokół ewaluacji

Obecny `GeneticIslandAlgorithm.step()` wykonuje kolejno migracje, selection,
reproduction, skalarne `evaluate()` i replacement. Integracja wymaga jawnych
faz bez zmiany ścieżki CPU:

```python
offspring = algorithm.prepare_step_for_evaluation()
# asynchroniczny request GPU
algorithm.complete_step_after_evaluation(evaluated_offspring)
```

Dotychczasowe `step()` pozostaje równoważnym wrapperem:

```python
offspring = self.prepare_step_for_evaluation()
offspring = self.evaluate(offspring)
self.complete_step_after_evaluation(offspring)
```

Analogicznie inicjalizacja w shardzie wykonuje `create_initial_solutions()`,
ewaluację przez batcher i dopiero `init_progress()`. Refaktor nie może zmienić
kolejności migracji, liczników, replacement, snapshotów ani finalizacji w
istniejącym CPU runnerze. Test parity porównuje legacy `step()` z ręcznym
wykonaniem dwóch faz przy identycznych wejściach i RNG.

## 8. Kontrakt requestu ewaluacji

Każdy request logicznej wyspy zawiera:

```json
{
  "schema_version": 1,
  "request_id": "<run>:<island>:<sequence>",
  "run_id": "...",
  "island_id": 17,
  "shard_id": 1,
  "phase": "offspring",
  "step": 42,
  "evaluations_before": 180,
  "problem_id": "r01_elliptic",
  "dimension": 200,
  "instance_seed": 20260511,
  "rows": 4,
  "row_context": [
    {"index": 0, "logical_evaluation": 180},
    {"index": 1, "logical_evaluation": 181},
    {"index": 2, "logical_evaluation": 182},
    {"index": 3, "logical_evaluation": 183}
  ]
}
```

Macierz kandydatów jest osobnym argumentem NumPy `[rows,dimension]`. Batcher
sprawdza unikalność request ID, długość `row_context`, dtype, skończoność oraz
zgodność klucza `(problem_id,dimension,instance_seed,dtype)`. Nie miesza różnych
kluczy w jednym wywołaniu backendu. Odpowiedź zachowuje kolejność requestów i
wierszy; shard dodatkowo sprawdza request ID i oczekiwaną liczbę wyników przed
modyfikacją solution.

Brak cichego fallbacku CPU. Błąd GPU kończy wszystkie requesty danego batcha
tym samym błędem i cały run ma status `failed`.

## 9. Polityka wspólnego batchera

W profilu 200 wysp:

```text
initial:  200 * 16 = 3200 kandydatów
steady:   200 * 4  =  800 kandydatów przy pełnym zbiegu requestów
```

Pierwszy canary używa parametrów jawnych w CLI i metadanych:

```text
initial_target_batch_rows = 3200
initial_max_wait_ms       = 50.0
steady_target_batch_rows  = 800
steady_max_wait_ms        = 2.0
max_batch_rows            = 3200
max_pending_per_island = 1
```

Dłuższy timeout inicjalizacji nie wpływa na signed delays, ponieważ pomiar
migracji zaczyna się dopiero po inicjalizacji i barierze startowej. Krótki
timeout fazy steady ogranicza dodatkowe sprzężenie czasowe między wyspami;
2 ms jest krótsze niż każdy zmierzony roundtrip B=800. Canary ma sprawdzić,
czy wystarcza do zebrania sensownego batcha przy rzeczywistym napływie z
12 shardów. Jeśli nie, decyzję zmieniamy jawnie i zapisujemy w metadanych.

`target_batch_rows` nie jest barierą. Dispatch następuje po pierwszym z:

- osiągnięcie targetu (`reason=size`);
- upływ czasu najstarszego requestu (`reason=timeout`);
- jawny flush przy końcu runa (`reason=flush`).

Target zależy od pola `phase` (`initial` albo `offspring`). Request większy od
wolnego miejsca można podzielić na fragmenty, ale odpowiedź
wraca do callera dopiero po złożeniu wszystkich jego fragmentów w pierwotnej
kolejności. Backendowy limit 8192 pozostaje twardy. Finalne wartości target/wait
muszą wynikać z `validation.json` joba 3168014 i małego canary GA; nie wolno ich
dostrajać na podstawie wyniku optymalizacji.

## 10. Telemetria batchera

Batcher zapisuje buforowane rekordy, bez synchronicznego I/O w gorącej ścieżce:

- request ID, island/shard, phase, step i zakres logical evaluations;
- enqueue, dispatch, GPU completion i caller completion;
- czas oczekiwania requestu i powód dispatchu;
- batch ID, liczba requestów/wierszy/unikalnych wysp;
- rozmiar, H2D, kernel, D2H/pending wait, actor time i Ray roundtrip;
- fragmentację requestów oraz przywrócenie kolejności;
- high-water mark kolejki, timeouty, błędy i anulowania.

Artefakty:

```text
metrics/athena/evaluation_requests.jsonl.gz
metrics/athena/gpu_batches.jsonl.gz
metrics/athena/shards.json
metrics/athena/backend.json
```

Nie zastępują istniejących plików per wyspa. `run_metadata.json` wskazuje oba
profile i opisuje wpływ batchowania na obserwowaną asynchroniczność.

## 11. Migracje i kolejki

`MigrationRouter` utrzymuje 200 osobnych list, liczników i sekwencji fetch.
Źródłowa wyspa nadal:

1. wybiera migrantów przy tej samej różnicy liczników ewaluacji;
2. losuje cel ze swojej dokładnej listy sąsiadów;
3. tworzy te same `event_id`, `batch_id` i pola send;
4. wysyła osobny rekord każdego migranta.

Router dodaje enqueue/dequeue timestamps, destination placement i queue depth.
`drain(island_id)` na pierwszym etapie zachowuje nawet historyczną semantykę
mutowania listy podczas iteracji, która może zostawić część wiadomości do
następnego fetch. Jej naprawa zmieniłaby eksperyment i wymaga osobnej decyzji.

Każda logiczna wyspa zachowuje pipeline jednego rozpoczętego fetchu. Na końcu
runu router rozróżnia:

- przetworzone eventy;
- `prefetched_not_processed_at_end_of_run`;
- `queued_not_dequeued_at_end_of_run`.

Intra-shard i inter-shard przechodzą przez ten sam router. Nie optymalizujemy
lokalnych migracji inną ścieżką, bo zmieniłoby to czasy i kolejki zależnie od
mappingu shardów.

## 12. Bariery bez zakleszczeń

Stare bariery na 200 aktorach nie mogą być wywoływane kolejno przez logiczne
wyspy w jednym shardzie.

- **Start:** driver najpierw odbiera `ready` od wszystkich shardów, batchera,
  routera i GPU. Dopiero potem jednym poleceniem uruchamia shardy. Logiczne
  `wait_for_all_start()` staje się sprawdzeniem tokenu startowego, nie blokującą
  barierą per wyspa.
- **Finish:** każda wyspa sygnalizuje zakończenie po zapisaniu własnych legacy
  artefaktów. Shard z wyspą 0 zawsze obsługuje ją jako ostatnią w swoim lokalnym
  porządku; jej historyczne oczekiwanie może wtedy blokować shard bez
  zatrzymywania jego niedokończonych wysp. Pozostałe shardy nadal pracują.
- **Delivery:** najpierw wszystkie logiczne wyspy potwierdzają swoje ostatnie
  refy wysyłki bez bariery. Dopiero potem shard zgłasza routerowi liczbę
  zakończonych wysp; wspólna bariera działa na poziomie shardów/liczników.
- **Metrics:** snapshot końcowych kolejek następuje dopiero po delivery barrier.

Każda bariera ma timeout, raport liczników i listę brakujących island IDs.
Timeout kończy run; nie ma retry aktora ani automatycznego resubmitu.

## 13. Metryki i zgodność artefaktów

Dla każdej z 200 wysp nadal są wymagane:

```text
resultsEveryStepW<ID>.json
W<ID> Imigrants.json
kontrolW<ID>End.ctrl.txt
metrics/island_<ID>/migration_events.jsonl.gz
metrics/island_<ID>/queue_fetches.jsonl.gz
metrics/island_<ID>/fitness_history.jsonl.gz
metrics/island_<ID>/final_solution.json
metrics/island_<ID>/runtime.json
metrics/island_<ID>/summary.json
```

Pola runtime zachowują dotychczasowe znaczenie, a placement rozszerza się o:

```text
physical_actor_kind=IslandShard
shard_id
shard_island_ids
gpu_batcher_policy
evaluation_request_count
evaluation_batch_ids
evaluation_queue_wait_seconds
evaluation_roundtrip_seconds
```

`data_contract.json` pozostaje zgodny w części migracyjnej. Nowy dokument
`athena_evaluation_contract.json` opisuje request/batch telemetry. Walidator
końcowy wymaga dokładnie 200 katalogów wysp, zgodnych liczników ewaluacji,
unikalnych event/request IDs i pełnego rozliczenia wszystkich wysłanych
migrantów oraz requestów ewaluacji.

## 14. Proponowany podział modułów

Wszystkie nowe entrypointy i aktory pozostają pod `athena_gpu/`:

```text
athena_gpu/
  island_integration.py       # konfiguracja, shard plan, kontrakty i walidacja
  evaluation_batcher.py       # async EvaluationBatcher
  gpu_evaluator.py            # jedyny właściciel CupyBatchBackend
  migration_router.py         # 200 logicznych kolejek i telemetry
  island_shard.py             # RNG contexts i maszyny stanów wysp
  run_island_canary.py        # driver, metadata, final validation
  run_island_canary.sh        # compute-node wrapper, bez automatycznego retry
  submit_island_canary.sh     # przyszły ręczny submitter
  tests/
```

Wspólny kod GA otrzymuje tylko minimalny, neutralny refaktor dwóch faz kroku.
Istniejący `hpc_benchmarks/run_benchmark.py`, launchery Aresa i CPU `IslandRunner`
nie importują modułów `athena_gpu` i zachowują dotychczasowy przebieg.

## 15. Kolejność implementacji i bramki

1. Pure unit tests: shard mapping, RNG isolation, request splitting/order,
   timeout/flush, queue drain, event reconciliation i failure fan-out.
2. Refaktor `step()` z parity testem starej i rozdzielonej ścieżki CPU.
3. Lokalny fake backend: kilka wysp, mały budżet, wszystkie migracje i metryki,
   bez Ray/CUDA.
4. Lokalny Ray z `NumpyBatchBackend`: shardy + batcher + router, bez GPU.
5. Ręcznie zatwierdzony A100 canary: kilka wysp, 128/256 ewaluacji, maksymalnie
   15 minut = 0.25 GPUh.
6. 200 wysp, krótki budżet, nadal jedna A100 i twardy walltime.
7. Jeden pełny repeat 8000 dopiero po walidacji artefaktów i kosztu.

Każdy etap kończy się osobnym raportem. Przejście dalej wymaga:

- braku deadlocku i aktorów `num_cpus=0`;
- dokładnego budżetu ewaluacji per wyspa;
- zachowania seedów w testach przeplotu;
- kompletnej migracji i research telemetry;
- dowodu rzeczywistego GPU (`h2d=1`, `d2h=1`, kernel time > 0);
- rozliczenia każdego evaluation requestu;
- czystego, przypiętego commita;
- ręcznego submitu użytkownika, bez retry/resubmitu.

## 16. Pierwsze parametry canary, nie kampanii

Pierwszy przyszły canary powinien być mały i jawnie diagnostyczny:

```text
logical islands: 8 lub 12
shards:          4
benchmark:       r01_elliptic D=200
population:      16
offspring:       4
evaluations:     128 lub 256 na wyspę
topology:        jawny mały torus diagnostyczny
migration:       5/5, best/plain
GPU:             1 A100
SLURM CPU:       16
walltime:        15 min
max cost:        0.25 GPUh
retry:           disabled
```

Nie przygotowujemy jeszcze komendy submitu dla 200×8000. Najpierw musi istnieć
kod, lokalne testy, dry-run z pełnym resource planem i walidator małego canary.
