# Benchmarks refined: 30 CEC2014 + 10 binarnych

Pakiet poprawia dotychczasowy zestaw 40 problemów. Część ciągła korzysta z oficjalnych danych CEC2014 i jest porównana numerycznie z oficjalnym programem C. Część binarna zachowuje dotychczasowe funkcje celu, w tym ujemny merit factor LABS oraz tę samą instancję NK z K=4.

Nowe identyfikatory to `r01_...`–`r30_...` oraz `b01_...`–`b10_...`. Historyczne `c01_...`–`c30_...` i `d01_...`–`d10_...` nadal wybierają wcześniejszy kod. Dzięki odrębnym czteroznakowym prefiksom poprawione funkcje mają osobne katalogi wyników. Istniejące konfiguracje macierzy trzeba jawnie przełączyć na nowe nazwy, żeby używały tego pakietu.

Pełne definicje, źródła, rozbieżności między wzorami w raporcie CEC i oficjalnym kodem oraz ograniczenia porównywalności opisuje [RESEARCH.md](RESEARCH.md).

## Wymiary i zależności

- CEC2014: **D = 10, 30, 50, 100**, domyślnie 30; każda współrzędna w `[-100, 100]`. D=200 jest odrzucane, ponieważ nie jest objęte dołączonymi oficjalnymi instancjami Part A.
- Problemy binarne: domyślnie **60 bitów**. Trap5 wymaga wielokrotności 5, Trap4 i RoyalRoad4 wielokrotności 4. LABS wymaga co najmniej 2 bitów, NK co najmniej 5, MaxCutRing co najmniej 3. Pozostałe funkcje dopuszczają dodatnią długość. Długości 60, 100 i 200 pasują do całej dziesiątki.
- Same ewaluatory: Python 3.10+ i NumPy; API użyte w kodzie jest zgodne ze stosowaną w projekcie wersją NumPy 1.21.4. Adaptery: dotychczasowy **jmetalpy==1.5.5**. Pełny test integracji wymaga także zależności istniejącego projektu, w tym Ray.
- Nie dochodzi żadna nowa biblioteka produkcyjna. Nie trzeba instalować zewnętrznego pakietu benchmarków, kompilować C ani pobierać danych na węźle obliczeniowym. Pliki w `data/` i `tests/reference/` należy przenieść razem z kodem.

## Sprawdzenie w aktywnym venv, również na Aresie

Uruchom z zewnętrznego katalogu `islands_desync/` tego repozytorium:

```bash
cd ~/islandsEA_student_fork/islands_desync
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export MPLBACKEND=Agg

python --version
python -m islands_desync.geneticAlgorithm.utils.benchmarks_refined --list
python -m islands_desync.geneticAlgorithm.utils.benchmarks_refined \
  --validate --output benchmark_validation.json
```

Pełne sprawdzenie nie uruchamia klastra Ray ani zadania SLURM. Wykonuje porównania funkcji, krótkie przebiegi jMetalPy oraz pierwszy krok rzeczywistego algorytmu wyspowego z lokalnym zastępstwem komunikacji jednej wyspy. Oczekiwany wynik to **13 testów, 0 błędów, 0 pominięć**, `success: true` i kod zakończenia 0. Brak zależności integracji daje błąd, a nie pozornie udany pominięty test.

Do weryfikacji samych wzorów wystarcza:

```bash
python -m islands_desync.geneticAlgorithm.utils.benchmarks_refined \
  --validate --core-only --output benchmark_core_validation.json
```

Ten wariant wykonuje 9 testów i nie potwierdza integracji z algorytmem. [Dołączony raport](validation_report.json) pochodzi z Windows, Python 3.12.14, NumPy 1.26.4, jMetalPy 1.5.5 i Ray 2.31.0. **Uruchomienie pod Pythonem 3.10 i właściwym stosem Aresa pozostaje do sprawdzenia na Aresie.** Raport zapisuje rzeczywiste wersje środowiska; pakiet nie wymaga zmiany projektowego Ray 2.9.3 na wersję z lokalnego testu.

Zmienne ograniczające wątki BLAS trzeba ustawić przed uruchomieniem Pythona i przekazać wszystkim workerom. Cel to jeden wątek obliczeń liniowych na przypisany CPU, bez nadmiernej liczby wątków przy wielu wyspach. Dokładny mechanizm zależy od biblioteki BLAS używanej przez NumPy; zob. [dokumentacja NumPy](https://numpy.org/doc/stable/reference/global_state.html).

## Użycie w istniejącym runnerze

Aktywna fabryka `create_algorithm_hpc.py` rozpoznaje nowe nazwy poprzez dotychczasową fabrykę `benchmark_problems.py`. W konfiguracji lokalnego batcha podaj nową nazwę w polu `problem`. Przy bezpośrednim uruchomieniu użyj istniejących zmiennych:

```bash
export ISLANDS_PROBLEM=r29_composition7
export ISLANDS_NUMBER_OF_VARIABLES=30
```

Dla problemu binarnego analogicznie:

```bash
export ISLANDS_PROBLEM=b03_nk_k4
export ISLANDS_NUMBER_OF_VARIABLES=60
```

Następnie uruchom dotychczasowy runner z parametrami eksperymentu. Nie trzeba zmieniać operatorów: istniejąca fabryka dobiera BitFlip/SPX dla problemów binarnych oraz dotychczasowe operatory ciągłe dla CEC. Populacja, budżet ewaluacji, topologia i migracja są nadal parametrami algorytmu.

Wyspa 0 zapisuje `benchmark_manifest.json` obok `param.json`, podczas konstrukcji algorytmu, przed pętlą ewolucji. Eksporter wyników kopiuje ten plik, jeśli istnieje. Manifest zawiera nazwę, wymiar, kierunek optymalizacji, wersję i SHA-256 kodu pakietu; dla CEC także identyfikator funkcji i pochodzenie danych, dla NK seed, sąsiedztwo i komplet tablic instancji. SHA kodu obejmuje główne moduły pakietu po ujednoliceniu końców linii, więc zwykłe LF/CRLF nie zmienia identyfikatora. Nie jest to hash całego algorytmu; zachowuj również commit repozytorium i konfigurację uruchomienia.

## Użycie bez runnera

```python
from islands_desync.geneticAlgorithm.utils.benchmarks_refined import (
    create_evaluator, create_problem,
)

f = create_evaluator("r13_happycat", 30)
assert abs(f(f.optimum_position) - 1300.0) < 1e-8
value = f([0.0] * 30)             # wartość celu z biasem CEC
error = value - f.optimum_value  # błąd względem optimum, do analizy

labs = create_evaluator("b01_labs_binary", 60)
value = labs([0, 1] * 30)        # ujemny merit factor
assert labs.optimum_value is None

problem = create_problem("b02_trap5", 60)  # adapter jMetalPy
solution = problem.create_solution()
problem.evaluate(solution)
```

Ewaluatory nie losują podczas obliczania celu i nie zmieniają wejściowego wektora. Odrzucają zły wymiar, NaN/inf, ciągłe punkty poza granicami oraz wartości binarne inne niż 0/1. NK domyślnie używa `instance_seed=20260511`. Własny seed można przekazać przez API lub CLI manifestu; aktualny runner środowiskowy korzysta ze stałego domyślnego seeda. Seed instancji NK i seed losowania populacji to różne parametry.

Manifest bez uruchamiania GA:

```bash
python -m islands_desync.geneticAlgorithm.utils.benchmarks_refined \
  --manifest r29_composition7 --dimension 30 --output cec_instance.json
python -m islands_desync.geneticAlgorithm.utils.benchmarks_refined \
  --manifest b03_nk_k4 --dimension 60 --output nk_instance.json
```

## Struktura i odtwarzanie odniesienia

| Plik | Rola |
|---|---|
| `cec_functions.py` | Wspólne jądra funkcji CEC i ich skale |
| `cec2014.py` | F1–F30, transformacje, hybrydy, kompozycje, dane instancji |
| `discrete.py` | Dotychczasowe 10 binarnych funkcji celu |
| `adapters.py` | Adaptery jMetalPy |
| `data/cec2014.npz`, `data/manifest.json` | Oficjalne dane oraz pochodzenie i sumy kontrolne |
| `tests/reference/cec2014_golden.json.gz` | 1776 wyników niezależnie uruchomionego oficjalnego C |
| `tests/test_*.py` | Testy numeryczne, regresyjne i integracyjne |
| `tools/prepare_cec_data.py` | Konwersja oficjalnych plików tekstowych do NumPy |
| `tools/generate_cec_reference.py` | Odtworzenie wyników referencyjnych przy użyciu kompilatora |

Zwykły użytkownik korzysta z gotowych danych i wyników odniesienia. Deweloper może odtworzyć je z przypiętego [oficjalnego archiwum](https://raw.githubusercontent.com/P-N-Suganthan/CEC2014/98488087d590c29aaded9978ccfe2a356d10dd63/cec14-c-code.zip):

```bash
PACKAGE=islands_desync/geneticAlgorithm/utils/benchmarks_refined
python "$PACKAGE/tools/prepare_cec_data.py" /path/to/cec14-c-code.zip
python "$PACKAGE/tools/generate_cec_reference.py" /path/to/cec14-c-code.zip \
  --work-dir /tmp/cec14-reference --compiler g++
python -m islands_desync.geneticAlgorithm.utils.benchmarks_refined --validate
```

Oba narzędzia sprawdzają SHA-256 archiwum przed użyciem. W Windows generator obsługuje `--compiler cl` po aktywacji środowiska kompilatora MSVC x64. Generator odniesienia nie importuje naszych funkcji CEC. W oficjalnym C wykonuje wyłącznie dwie poprawki przenośności: usuwa nieużywany nagłówek `WINDOWS.H` i poprawia format `scanf` z `%Lf` na `%lf` dla wskaźników `double*`. Nie zmienia wzorów.

Wyniki i tolerancje potwierdzają zgodność numeryczną dla sprawdzonych punktów, nie identyczność bitową między kompilatorami/BLAS. Zmiana poprawionej funkcji lub środowiska może zmienić czas ewaluacji, co ma znaczenie w badaniach opóźnień wysp. Nowe eksperymenty porównuj przy tej samej wersji pakietu i instancji, zachowując historyczne wyniki pod ich pierwotnymi nazwami.
