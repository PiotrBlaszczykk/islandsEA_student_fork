> Aktualizacja 2026-09-15: obowiązuje **144 wyspy**, torus **12×12**,
> complete oraz wybrane **ER4 / WS3 / BA**. Źródło aktualnych ustawień i status
> załączników: [STUDY_144.md](../STUDY_144.md). ER4 dostarczono jako 150 węzłów;
> jego uruchomienie przy 144 jest zablokowane do rozstrzygnięcia. Historyczne
> pomiary sprzętu pozostają niezmienione; D=200 oznacza wymiar benchmarku.

# Benchmarki w main: Ray i Ares

Do aktywnej ścieżki wyspowej przeniesiono z `help_codebase` pakiet **30 ciągłych + 10 binarnych** wraz z gotowymi danymi, testami i pochodzeniem instancji. Wzory i dane są identyczne z pakietem źródłowym. Launcher uruchamia istniejący `IslandRunner` i algorytm z **main**, z jego strategiami akceptacji migrantów.

## Środowisko i pierwszy test na Aresie

Komendy poniżej wykonuj z katalogu repozytorium, zawierającego `AGENTS.md`, `islands_desync/` i `hpc_benchmarks/`. Po przeniesieniu zmian na Aresa:

```bash
cd ~/islandsEA_student_fork
module load python/3.10.4-gcccore-11.3.0
source "$HOME/venvs/islands-ray/bin/activate"
export PYTHONPATH="$PWD/islands_desync${PYTHONPATH:+:$PYTHONPATH}"
python --version
python -m islands_desync.geneticAlgorithm.utils.benchmarks_refined --list
```

Trwałe dane i logi nie są zapisywane w repo ani bezpośrednio w HOME. Wrappery
`submit_*.sh` tworzą `$SCRATCH/islandsEA/{results,logs,checkpoints,tmp}` i
kierują tam wyniki, audyt, logi SLURM i ewentualne logi awarii Ray. Repo i venv
pozostają w HOME. Wspólnym źródłem ustawień jest `ares_storage.sh`; wszystkie
ścieżki można nadpisać zmiennymi `ISLANDS_*_ROOT`.

Korzystaj z działającego venv projektu. Pakiet nie dodaje zależności produkcyjnych: wystarczą dotychczasowy stos, NumPy i jMetalPy 1.5.5. Nie wymaga C, Internetu na workerach ani zmiany wersji Ray. Dla świeżego środowiska istnieje `smoke_run/setup_ares_venv.sh` z Pythonem 3.10 i pinami Ray 2.9.3; zawiera ścieżki konta `plgblaszczykk`. Nie uruchamiaj go ponownie tylko z powodu dodania benchmarków, jeśli masz już działające środowisko. Własną ścieżkę venv można ustawić przez `export ISLANDS_VENV_DIR=/sciezka/do/venv`.

Najpierw walidacja na węźle obliczeniowym, następnie dwa małe uruchomienia Ray:

```bash
bash hpc_benchmarks/submit_validation.sh

bash hpc_benchmarks/submit_ares.sh \
  --problem b03_nk_k4 --dimension 60 --diagnostic --islands 2 --evaluations 128 \
  --topology complete --strategy maxDistance --acceptance plain

bash hpc_benchmarks/submit_ares.sh \
  --problem r29_composition7 --dimension 200 --diagnostic --islands 2 --evaluations 128 \
  --topology complete --strategy best --acceptance plain
```

Jeśli konto wymaga wskazania grantu lub partycji, dodaj właściwe opcje przy ręcznym `sbatch`; skrypty ogólne nie wpisują cudzego grantu. Walidacja zapisuje `$SCRATCH/islandsEA/results/validation/validation-<JOBID>.json`; oczekiwane: **17 testów, zero błędów i pominięć, `success: true`**. Każdy pilot powinien zakończyć się kodem 0 i linią `BENCHMARK_RUN_OK=...` w `$SCRATCH/islandsEA/logs/slurm/benchmark-<JOBID>.out`. Zweryfikuj również `State` i `ExitCode` przez `sacct`.

Domyślna konfiguracja badawcza to 144 wyspy i 7×48 CPU. Dla diagnostyki 1–2 wysp `submit_ares.sh` wybiera 1 węzeł × 6 CPU; wymagane jest `--diagnostic`. Właściwe badania uruchamiaj przez `submit_ares_144.sh`.

## Parametry pełnego eksperymentu

Sprawdzenie konfiguracji bez Ray i bez utworzenia wyników:

```bash
python hpc_benchmarks/run_benchmark.py \
  --problem r29_composition7 --dimension 200 --islands 144 \
  --topology torus --strategy best --acceptance plain --dry-run
```

Przykład dla 144 wysp, 8000 ewaluacji na wyspę, populacji 16, czterech potomków, pięciu migrantów i interwału 5:

```bash
source hpc_benchmarks/ares_storage.sh
islandsea_configure_storage
sbatch --nodes=7 --cpus-per-task=48 --time=01:00:00 \
  --output="$ISLANDS_SLURM_LOG_DIR/benchmark-%j.out" \
  --error="$ISLANDS_SLURM_LOG_DIR/benchmark-%j.err" \
  hpc_benchmarks/run_ares.sh \
  --problem r29_composition7 --dimension 200 --islands 144 \
  --evaluations 8000 --population 16 --offspring 4 \
  --migrants 5 --interval 5 --topology torus \
  --strategy best --acceptance plain --repeat 1 --seed 20260912
```

Godzina jest przykładowym limitem kolejki, a nie zmierzonym czasem eksperymentu. Dobierz go po pilocie. Skrypt przydziela po 2 GB/CPU; nadpisanie parametrów `sbatch` zmienia alokację, a parametry za nazwą skryptu zmieniają eksperyment.

W obecnym kodzie `Island` i `Computation` rezerwują po 1 CPU na wyspę, a `SignalActor` jeszcze 1 CPU. Potrzeba zatem **`2*N+1` logicznych CPU Ray**. Wrapper dodatkowo zostawia jeden CPU głównego węzła dla procesu sterującego. Dla standardowych węzłów Aresa z 48 rdzeniami daje to:

| Wyspy | Minimum CPU Ray | Przykładowa alokacja | CPU dostępne dla Ray |
|---:|---:|---:|---:|
| 2 | 5 | 1 × 6 | 5 |
| 144 | 289 | 7 × 48 | 335 |

48 rdzeni dotyczy standardowego węzła CPU opisanego w [dokumentacji Aresa](https://docs.hpc.cyfronet.pl/supercomputers/ares/). To rezerwacje obecnej architektury aktorów, nie obietnica stałego wykorzystania wszystkich CPU. Ich zmiana mogłaby wpływać na harmonogram i opóźnienia, dlatego nie jest częścią portu benchmarków.

### Bezpieczny profil dla 144 wysp

`run_ares_144.sh` utrwala profil 7 × 48 CPU, konto `plglscclass26-cpu`, partycję `plgrid`, 30-minutowy bezpiecznik walltime oraz 300 sekund na start siedmiu węzłów. Skrypt zawsze dopisuje `--islands 144`; nie należy dodawać własnego `--islands`. Najpierw uruchom krótki canary, który tworzy pełne 289 aktorów Ray, lecz wykonuje mały budżet ewaluacji:

```bash
bash hpc_benchmarks/submit_ares_144.sh \
  --problem r29_composition7 --dimension 200 --evaluations 128 \
  --population 16 --offspring 4 --migrants 5 --interval 5 \
  --topology complete --strategy best --acceptance plain \
  --repeat 1 --seed 20260912
```

Po sukcesie canary (`State=COMPLETED`, `ExitCode=0:0`, `BENCHMARK_RUN_OK`) można uruchomić właściwy budżet. Limit czasu zwiększaj na podstawie zmierzonego przebiegu; opcja `sbatch` podana przed nazwą skryptu nadpisuje domyślne 30 minut:

```bash
ISLANDS_WALLTIME=01:00:00 bash hpc_benchmarks/submit_ares_144.sh \
  --problem r29_composition7 --dimension 200 --evaluations 8000 \
  --population 16 --offspring 4 --migrants 5 --interval 5 \
  --topology complete --strategy best --acceptance plain \
  --repeat 1 --seed 20260912
```

Przed startem Ray launcher wykonuje pełny `--dry-run`, sprawdza topologię i porównuje `2*N+1` z rzeczywistą alokacją. Za mały przydział kończy job kodem 2, zamiast pozostawić oczekującego aktora do walltime. Następnie każdy węzeł jednorazowo buduje własny cache Matplotlib w `/tmp/$USER/islandsea-$SLURM_JOB_ID/matplotlib`; workery dzielą gotowy cache tylko w obrębie lokalnego systemu plików węzła. Katalog tymczasowy jest usuwany z każdego węzła podczas kontrolowanego zakończenia.

Pięć topologii badania to torus12×12, complete, ER4, WS3 i BA. WS3/BA wczytują dokładne załączniki. ER4 ma w dostarczonym pliku 150 węzłów, dlatego preflight blokuje go przy wymaganych 144. Szczegóły i źródła grafów: [STUDY_144.md](../STUDY_144.md).

Każdy węzeł uruchamia jeden proces Ray przez `srun`. Readiness head node jest
sprawdzany bezpośrednio z procesu batch, który już działa na pierwszym węźle;
nie tworzy dodatkowego kroku `srun` konkurującego z blokującym procesem head.
Proces sterujący współdzieli przydział głównego węzła przez jawne
`--overlap --exact`, z CPU wyłączonym z puli Ray. Znaczenie `--exact` i
`--overlap` określa [dokumentacja SLURM](https://slurm.schedmd.com/srun.html).
Wrapper kończy własne kroki zadania; nie wykonuje globalnego `ray stop`.

Gotowy pełny pilot F1/D200, torus 12×12, `best/plain`, trzy powtórzenia oraz jego ścisły walidator są opisane w [`pilot_run/README.md`](../pilot_run/README.md). Nie składaj go ręcznie z trzech osobnych komend: skrypt zgłoszeniowy zapisuje wspólny manifest i uruchamia finalizer zależny od całej tablicy.

## Dobór benchmarku i topologii

- `r01_...`–`r30_...`: D=10/30/50/100 z oficjalnymi danymi CEC2014; **D=200 jest rozszerzeniem IslandsEA**, oznaczonym `official_cec2014_instance: false`. Nie należy przedstawiać go jako oficjalnej instancji CEC2014 200D.
- `b01_...`–`b10_...`: długość w bitach; 60, 100 i 200 pasują do wszystkich dziesięciu problemów. Definicje i ograniczenia: [README pakietu](../islands_desync/islands_desync/geneticAlgorithm/utils/benchmarks_refined/README.md), [raport naukowy](../islands_desync/islands_desync/geneticAlgorithm/utils/benchmarks_refined/RESEARCH.md).
- Zachowane `sphere` i `rastrigin` przyjmują dodatni wymiar, także 200. Uruchamianie starego `start.py` bez wyboru problemu zachowuje domyślne `Sphere` i parametry JSON.
- Selekcja migrantów: `random`, `best`, `worst`, `maxDistance`. Akceptacja: dotychczasowe `plain`, `better`, `newer`, `older`, `oldest`, `stochastic`, `rejectTooOld`, `window`, z istniejącą składnią `dup_` i `:liczba`.

Launcher używa dokładnie istniejących grafów. **Nie wszystkie obsługują dowolną liczbę wysp:**

| CLI | Ograniczenie obecnej implementacji |
|---|---|
| `complete` | Dowolna dodatnia liczba wysp |
| `ring` | Do eksperymentów używaj co najmniej 3 wysp; istniejący graf zawiera również sąsiedztwo własne |
| `torus` | Domyślnie historyczne `12 × (N/12)`, N≥24 i podzielne przez 12; opcjonalnie jawne `rows × columns = N` |
| `er1`–`er4` | Gotowe grafy na 150 wysp |
| `ws3`, `ws4` | Gotowe grafy na 144 wyspy |

Preflight sprawdza rzeczywiste listy sąsiadów i przerywa przy niezgodności, np. domyślny torus150 albo ER180. Jawny prostokątny torus rozwiązuje wyłącznie kwestię rozmiaru tej rodziny; do porównania ER, WS i torusa przy **tej samej** liczbie 150–144 wysp nadal potrzebne będą osobno uzgodnione, zapisane grafy ER/WS. Port benchmarków nie generuje tych grafów ani nie poprawia istniejących pętli własnych. Nawet przy grafie pełnym dotychczasowy `RandomSelect` wybiera jeden cel na migranta; nie jest to rozesłanie każdego migranta do wszystkich sąsiadów.

## Zachowane znaczenie parametrów

`--interval` odpowiada istniejącemu warunkowi `evaluations - last_migration_evolution >= migration_interval`. **Jednostką jest przyrost licznika ewaluacji**, nie liczba pokoleń. Przy czterech potomkach interwał 5 zwykle oznacza kolejne wysyłki co 8 ewaluacji po pierwszej wysyłce. Zmiana tego na pięć pokoleń wymagałaby osobnej decyzji o metodzie badań. Znak opóźnienia pozostaje `source_epoch_at_send - destination_epoch_at_receive`.

Fabryka dobiera BitFlip(1/liczba bitów) + SPX dla binarnych oraz dotychczasowe MyUniformMutation(1/D, perturbation=10) + SwitchCrossover dla ciągłych. Selekcja rodziców pozostaje BinaryTournamentSelection. Odległość binarna liczona jest po bitach (Hamming), a wymiar w logach oznacza liczbę bitów. Dla float zachowano dotychczasowe sumowanie kwadratów różnic i wybór `maxDistance`.

`--repeat` wskazuje numer jednego powtórzenia; nie uruchamia wielu prób automatycznie. Seed wyspy i to `seed + (repeat-1)*1000000 + i`. Nie zmienia to stałych instancji benchmarków, np. NK ma osobny seed instancji 20260511. Asynchroniczne przyjścia migrantów zależą od harmonogramu, więc ten sam seed nie gwarantuje identycznego przebiegu na HPC. Nie nadpisuj danych benchmarków między powtórzeniami.

## Wyniki i kontrola węzłów

Gotowe NPZ są w repozytorium; nie generuje się macierzy na workerach. Ustawienia BLAS/OMP=1 oraz parametry są przekazywane przez `runtime_env` Ray. Przed pętlą eksperymentu launcher sprawdza każdy węzeł: import i ewaluację problemu, identyczność instancji, kodu, konfiguracji, Pythona i wersji głównych zależności. Zapisuje dostępne zasoby i odmawia uruchomienia przy niedoborze CPU.

Zachowane surowe wyniki trafiają domyślnie do `$SCRATCH/islandsEA/results/runs/<data>/<prefiks><wymiar>/<czas>_<id> .../`. Znajdziesz tam dotychczasowe CSV/JSON, statystyki i podpisane opóźnienia migrantów oraz:

- `benchmark_manifest.json`: instancja, oficjalne lub projektowe dane, SHA-256 wzorów, rzeczywiste operatory;
- `param.json`: dotychczasowe pola plus `active_operators` (stare tekstowe pole `operators` jest historyczne; używaj nowego pola do identyfikacji operatorów);
- `experiment_manifest.json`: pełne argumenty, konfiguracja, seedy, wersje, commit i stan dirty, hash kodu runtime i launchera, kontrola węzłów, status wykonania;
- `run_metadata.json`: agregowalne metadane konfiguracji naukowej, run/repeat/seed, topologii, zasobów, proweniencji i rozstrzygniętych ścieżek storage;
- `topology.json`: dokładne skierowane listy sąsiadów, także pętle własne; `topology.png`: pomocniczy rysunek po zakończeniu, bez pełnego odwzorowania kierunków i pętli;
- `iterations_per_second.json`: wyniki czasowe zwrócone przez wyspy.

Kopia manifestu, metadanych i topologii jest w `$SCRATCH/islandsEA/results/audit/<data>_<czas>_<id>/`. Zachowuje również informację o błędzie nieudanego startu. Losowy identyfikator chroni przed kolizją nazw uruchomień; benchmarki mają unikalne prefiksy czteroznakowe. `--output-root` i `--audit-root` pozwalają jawnie zmienić te lokalizacje.

W manifeście `configuration` oznacza JSON z nadpisanymi czterema parametrami GA i problemem. Aktywna liczba wysp, migranci, interwał i strategie pochodzą z `args`; pozostawione historyczne pola JSON o podobnych nazwach nie sterują migracją w tej ścieżce.

## Co sprawdzono lokalnie

[validation_local.json](validation_local.json) dokumentuje zgodność plików z `help`, kontrolę niezmienności kluczowych metod migracji względem zastanego `main`, 17 testów oraz dwa zakończone przebiegi po 2 wyspy Ray i 128 ewaluacji na wyspę: NK60 z `maxDistance` i F29 200D z `best`. Oba zapisały wyniki każdej wyspy i odebranych migrantów. Testy wykonano na Windows z Pythonem 3.12.14 i Ray 2.31.0; nie zastępują walidacji na Pythonie 3.10 ani wielowęzłowym SLURM Aresa.

Lokalny odpowiednik pilota, w środowisku z zależnościami projektu:

```bash
python hpc_benchmarks/run_benchmark.py \
  --problem b03_nk_k4 --dimension 60 --diagnostic --islands 2 --evaluations 128 \
  --topology complete --strategy maxDistance --ray-address local --local-cpus 6
```
