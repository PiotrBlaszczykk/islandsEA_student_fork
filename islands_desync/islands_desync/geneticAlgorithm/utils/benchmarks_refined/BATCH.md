# Batch CPU/CuPy dla Atheny

Stan 2026-09-14: zaimplementowane te same **30 CEC2014 + 10 binarnych**;
NumPy sprawdzone lokalnie. Pełna walidacja CuPy na A100 jest przygotowana,
ale **nie została jeszcze uruchomiona**. Historyczny test F1 z joba 3167902
dotyczył wcześniejszego kodu i nie certyfikuje nowego backendu.

## API i integracja

```python
import numpy as np
from islands_desync.geneticAlgorithm.utils.benchmarks_refined.batch import (
    NumpyBatchBackend, CupyBatchBackend,
)

backend = NumpyBatchBackend()  # jawny wybór CPU
# W długowiecznym aktorze Ray num_gpus=1: backend = CupyBatchBackend()
backend.prepare("r29_composition7", 200)  # raz na instancję
x = np.zeros((800, 200), dtype=np.float64)
y = backend.evaluate_batch("r29_composition7", x)
metadata = backend.metadata("r29_composition7", 200)
assert y.shape == (800,) and y.dtype == np.float64
```

- Nazwy są identyczne z `BENCHMARKS`. Wymiar wynika z drugiej osi wejścia.
- Wejście jest tablicą **hosta** `[B,D]`; wynik to tablica hosta `[B]`, w tej
  samej kolejności. Backend nie modyfikuje wejścia i nie używa globalnego RNG.
- CEC: rzeczywiste wartości w `[-100,100]`, promowane do `float64`.
  Binary: bool albo liczby 0/1, promowane do `int64`; wynik `float64`.
  String, complex, NaN/Inf, zły kształt, wymiar lub zakres powodują błąd.
- `[0,D]` zwraca pusty wynik bez transferu kandydatów. Domyślnie `B <= 8192`;
  większy batch trzeba podzielić u wywołującego. Limit liczby rekordów nie
  jest limitem wszystkich buforów/pamięci ani mechanizmem backpressure.
- CEC obsługuje D=10/30/50/100 oraz **projektowe, nieoficjalne D=200**.
  Binarne zachowują dotychczasowe wymagania długości i podzielności bloków.
- Instancje są cache'owane po `(nazwa, wymiar, instance_seed)`.
  `instance_seed` ma domyślną wartość 20260511; zmiana ma sens tylko dla NK.
- `prepare()` ładuje zweryfikowane dane i przenosi stałe na GPU. Nie kompiluje
  wszystkich kerneli; przed pomiarem przepustowości trzeba wykonać warmup.
- Obiekt CuPy posiada prywatny stream. Wywołania jednego obiektu muszą być
  szeregowe. Nie przekazywać gotowego backendu przez Ray; konstruować go
  wewnątrz aktora, który posiada GPU. Brak CuPy/GPU kończy się błędem;
  backend CuPy nigdy automatycznie nie przełącza się na CPU.
- Identyfikatory wysp/requestów i przypisanie wyników należą do przyszłego
  batchera. Ta warstwa nie tworzy aktorów, kolejek ani barier generacji.
  Istniejące adaptery jMetalPy i fabryka GA nadal korzystają z CPU.

## Zachowana matematyka

`cec2014.py`, `cec_functions.py`, `discrete.py` oraz dane NPZ/golden pozostają
niezmienione. `batch.py` pobiera z nich nazwy kerneli, skale, grupy hybryd,
parametry kompozycji, dane instancji i metadane. `batch_kernels.py` dodaje
operacje z osią batcha, wspólne dla jawnie przekazanego NumPy/CuPy.
Ewaluatory skalarne służą do walidacji, nie do obliczania rekordów batcha.

Zachowane są m.in. skala przed rotacją, shuffle po pełnej rotacji, własne
dane F29/F30, divisor `1e30` i nierotowany komponent F23, dokładne zero
odległości z sentinelem `1e99` oraz normalizacja wag osobno dla każdego
rekordu. LABS nadal zwraca ujemny merit factor, z dokładną całkowitą energią;
zbyt duże N grożące przepełnieniem `int64` jest odrzucane. NK korzysta z tych
samych tabel i kolejności bitów. Pętle po komponentach/lugach są dopuszczone;
nie ma pętli Python po osobnikach.

Metadane zawierają SHA-256 danych/definicji i niepusty
`implementation_sha256`, wersję pakietu, `batch_version=1.0.0`, backend,
typ wyniku i limit batcha. Hash implementacji obejmuje moduły `.py` pakietu,
więc zmienia się po dodaniu warstwy batchowej także dla starego API;
hash danych pozostaje ten sam.

## Transfery i pomiary

Po przygotowaniu instancji niepusty batch CuPy wykonuje jeden transfer
kandydatów H2D i jeden transfer wyników D2H. Nie ma odczytów hosta ani
synchronizacji pomiędzy podfunkcjami. Stałe pozostają w pamięci backendu.
`last_profile` opisuje ostatnie wywołanie:

| Pole | Znaczenie |
|---|---|
| `prepare_and_validation_seconds` | walidacja hosta i ewentualne przygotowanie instancji |
| `h2d_device_seconds` | czas między zdarzeniami CUDA wokół H2D |
| `kernel_device_seconds` | odcinek strumienia CUDA obejmujący ewaluację |
| `d2h_and_pending_compute_wait_seconds` | czas hosta w blokującym odczycie, obejmuje oczekiwanie na wcześniejsze obliczenia |
| `call_seconds` | całe wywołanie backendu z walidacją wyniku |
| `h2d_count`, `d2h_count` | transfery kandydatów/wyniku; nie obejmują stałych z `prepare()` |

Czas D2H nie jest izolowanym czasem kopiowania i nie należy dodawać go do
czasu kernela jako rozłącznej składowej. Zdarzenia mierzą odcinek strumienia,
nie wyłącznie aktywne instrukcje GPU. Ray actor time i roundtrip mierzy
zewnętrzny walidator. API odczytu jest dostosowane do
[CuPy 10.6 `asnumpy`](https://docs.cupy.dev/en/v10.6.0/reference/generated/cupy.asnumpy.html).

## Walidacja

Z katalogu repo, w środowisku z NumPy:

```bash
export PYTHONPATH="$PWD/islands_desync${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
python -m unittest islands_desync.geneticAlgorithm.utils.benchmarks_refined.tests.test_batch -v
python -m islands_desync.geneticAlgorithm.utils.benchmarks_refined.batch_validation \
  --output /tmp/athena_cpu_batch_validation.json
```

Na klastrze testy obliczeniowe uruchamiać wewnątrz alokacji compute;
artefakty kierować do `$SCRATCH`, zgodnie z launcherem Atheny.

Macierz obejmuje 150 instancji CEC (30 × 5 wymiarów) i 20 instancji binary
(10 × N=60/200): wszystkie 2220 committed punkty odniesienia C, znane optima,
B=1/4/16/32/256, brzegi dziedziny, dtype, puste batche, kolejność wyników,
brak mutacji, przeplatanie problemów, globalny RNG, hashe i błędne wejścia.
Tolerancje są jawne: CEC `rtol=1e-10, atol=1e-8` jak w istniejących testach C;
LABS/NK `2e-14, 2e-14` z uwagi na dzielenie i sumowanie float64; pozostałe
wyniki binarne dokładne (`0,0`). Nie luzować tolerancji po awarii GPU.

Lokalny [raport CPU](../../../../../athena_gpu/validation_cpu.json):
Python 3.12.14, NumPy 2.3.5, 40 funkcji, 170 instancji, 22016 porównań,
1667 odrzuconych niepoprawnych wejść. Nie jest to walidacja starego stosu
Atheny ani dowód działania GPU. Test `test_real_cupy_all_functions` jest
jawnie pomijany bez `ISLANDS_TEST_CUPY=1`; po ustawieniu tej zmiennej brak
CuPy/GPU powoduje błąd, nie pominięcie.

Przygotowany [walidator A100](../../../../../athena_gpu/README.md) wykonuje
tę samą macierz wewnątrz rzeczywistego aktora GPU, sprawdza przypięty stos
Atheny i dodatkowo mierzy B=200/400/800/1200/1600/2400/3200 dla sześciu
reprezentatywnych funkcji. Nie został zgłoszony do SLURM.
