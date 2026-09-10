# Zgodność i walidacja zestawu 40 benchmarków IslandsEA

Pakiet `benchmarks_refined` zawiera pełne F1–F30 CEC2014 Part A oraz dziesięć dotychczasowych problemów binarnych IslandsEA. Zachowuje dobór problemów i konwencję minimalizacji. Poprawiona część CEC wykorzystuje oficjalne wektory przesunięcia, macierze i permutacje, a jej wartości zostały porównane z niezależnie skompilowanym oficjalnym programem C w 1776 punktach. Część binarna zachowuje dotychczasową skalę wyników i instancję NK; testy regresji porównują ją bezpośrednio ze starszym kodem projektu.

CEC2014 Part A opisuje wyłącznie optymalizację rzeczywistoliczbową. Dziesięć problemów binarnych jest uzupełnieniem projektu i nie należy do oficjalnego zestawu CEC. Dla tej części zgodność oznacza jawne definicje matematyczne, zachowanie wcześniejszych funkcji celu oraz kontrolę względem literatury problemów pseudo-boolowskich. [Raport CEC, sekcje 1–2](https://github.com/P-N-Suganthan/CEC2014/blob/98488087d590c29aaded9978ccfe2a356d10dd63/Definitions%20of%20%20CEC2014%20benchmark%20suite%20Part%20A.pdf).

## Podstawa definicji i danych

Podstawą CEC jest raport J. J. Lianga, B. Y. Qu i P. N. Suganthana z grudnia 2013, jego lokalna wersja Markdown w `more_local_matrix_computation/Definitions_of_CEC2014_benchmark_suite_Part_A.md` oraz dystrybucja C z repozytorium P. N. Suganthana. W przypadkach, w których drukowany wzór i kod wykonawczy różnią się, implementacja przyjmuje zachowanie oficjalnego C. Taka decyzja umożliwia niezależne sprawdzenie wartości i odtworzenie konkretnych instancji; rozbieżności są wymienione poniżej. [Oficjalne repozytorium CEC2014](https://github.com/P-N-Suganthan/CEC2014).

| Element | Utrwalona wartość |
|---|---|
| Commit źródłowy CEC | `98488087d590c29aaded9978ccfe2a356d10dd63` |
| Archiwum | `cec14-c-code.zip`, oficjalne repozytorium |
| SHA-256 archiwum | `1a210560398ca7a50be6adf1e5e90602222519ef23b6e31aba8847e109761876` |
| Funkcje | F1–F30 |
| Wymiary | 10, 30, 50, 100 |
| Reprezentacja lokalna | `float64` przesunięcia i macierze; `int64` permutacje |
| Konwersja danych | Bez losowania, renormalizacji macierzy i zmiany kolejności współrzędnych |
| Kontrola integralności | SHA-256 archiwum przy konwersji; SHA-256 NPZ przy pierwszym użyciu CEC w procesie |

Plik `data/manifest.json` zawiera również sumy kontrolne 182 plików źródłowych i kształty tablic. Dane są pobierane względem lokalizacji modułu, więc katalog roboczy nie wyznacza użytej instancji. Załadowane tablice są buforowane wewnątrz procesu i oznaczone jako tylko do odczytu. Zmiana zawartości paczki danych bez aktualizacji manifestu powoduje błąd, a nie cichą zmianę funkcji.

Publiczny upstream nie zawierał jawnego pliku licencji w sprawdzonym archiwum/repozytorium. Manifest podaje pochodzenie danych i nie przypisuje im nowej licencji. Do normalnego uruchomienia wystarcza dołączona paczka danych; kod C służy jako odniesienie deweloperskie.

## Katalog ciągły: 30 funkcji

Wszystkie poniższe funkcje są minimalizowane na `[-100,100]^D`, dla D z powyższej listy. Wartość zwracana przez ewaluator obejmuje bias, a optimum F_i wynosi `100*i`. Nazwy odpowiadają kolejności oficjalnego raportu; prefiks `r` odróżnia je od historycznych instancji generowanych w IslandsEA. [Raport CEC, sekcja 1](https://github.com/P-N-Suganthan/CEC2014/blob/98488087d590c29aaded9978ccfe2a356d10dd63/Definitions%20of%20%20CEC2014%20benchmark%20suite%20Part%20A.pdf).

| ID w kodzie | Funkcja CEC | Optimum |
|---|---|---:|
| `r01_elliptic` | F1, shifted/rotated high conditioned elliptic | 100 |
| `r02_bent_cigar` | F2, shifted/rotated bent cigar | 200 |
| `r03_discus` | F3, shifted/rotated discus | 300 |
| `r04_rosenbrock` | F4, shifted/rotated Rosenbrock | 400 |
| `r05_ackley` | F5, shifted/rotated Ackley | 500 |
| `r06_weierstrass` | F6, shifted/rotated Weierstrass | 600 |
| `r07_griewank` | F7, shifted/rotated Griewank | 700 |
| `r08_rastrigin` | F8, shifted Rastrigin, bez rotacji | 800 |
| `r09_rot_rastrigin` | F9, shifted/rotated Rastrigin | 900 |
| `r10_schwefel` | F10, shifted modified Schwefel, bez rotacji | 1000 |
| `r11_rot_schwefel` | F11, shifted/rotated modified Schwefel | 1100 |
| `r12_katsuura` | F12, shifted/rotated Katsuura | 1200 |
| `r13_happycat` | F13, shifted/rotated HappyCat | 1300 |
| `r14_hgbat` | F14, shifted/rotated HGBat | 1400 |
| `r15_grie_rosen` | F15, expanded Griewank plus Rosenbrock | 1500 |
| `r16_schaffer_f6` | F16, expanded Scaffer F6 | 1600 |
| `r17_hybrid1` | F17, hybrid 1, trzy grupy | 1700 |
| `r18_hybrid2` | F18, hybrid 2, trzy grupy | 1800 |
| `r19_hybrid3` | F19, hybrid 3, cztery grupy | 1900 |
| `r20_hybrid4` | F20, hybrid 4, cztery grupy | 2000 |
| `r21_hybrid5` | F21, hybrid 5, pięć grup | 2100 |
| `r22_hybrid6` | F22, hybrid 6, pięć grup | 2200 |
| `r23_composition1` | F23, composition 1, pięć składników | 2300 |
| `r24_composition2` | F24, composition 2, trzy składniki | 2400 |
| `r25_composition3` | F25, composition 3, trzy składniki | 2500 |
| `r26_composition4` | F26, composition 4, pięć składników | 2600 |
| `r27_composition5` | F27, composition 5, pięć składników | 2700 |
| `r28_composition6` | F28, composition 6, pięć składników | 2800 |
| `r29_composition7` | F29, composition 7, hybrydy 1–3 | 2900 |
| `r30_composition8` | F30, composition 8, hybrydy 4–6 | 3000 |

### Transformacje funkcji bazowych

Dla funkcji podstawowej obliczane jest `z = M @ (s * (x - o))`, z pominięciem M tam, gdzie oficjalny kod wyłącza rotację. Następnie jądro nakłada własne przesunięcie wewnętrzne, jeśli jest potrzebne. Wektor o jest oficjalnym środkiem instancji. Skale są przypisane do jąder i obowiązują także wtedy, gdy jądro jest wywoływane jako część hybrydy. Wcześniejsza lokalna implementacja mieszała ogólne wersje funkcji z przekształceniami specyficznymi dla CEC.

| Jądro | Skala s | Przesunięcie wewnętrzne |
|---|---:|---|
| Elliptic, Bent Cigar, Discus, Ackley, Scaffer F6 | 1 | Brak |
| Rosenbrock | 2.048/100 | +1 |
| Weierstrass | 0.5/100 | Argument cosinusa zawiera +0.5 |
| Griewank | 600/100 | Brak |
| Rastrigin | 5.12/100 | Brak |
| Modified Schwefel | 1000/100 | +420.9687462275036 |
| Katsuura | 5/100 | Brak |
| HappyCat, HGBat | 5/100 | −1 |
| Expanded Griewank–Rosenbrock | 5/100 | +1 |

W Weierstrassie pozostaje suma dla k=0,…,20 i odjęcie wartości w początku układu. Katsuura używa 32 potęg dwójki i `floor(t+0.5)` zgodnie z C. Modified Schwefel zachowuje osobne gałęzie dla wartości powyżej 500 i poniżej −500 oraz kary zależne od wymiaru. Stała `418.9828872724338` jest zapisana z precyzją oficjalnego kodu; użycie zaokrąglonego `418.9829` zmienia wynik także w optimum. [Archiwum CEC, `cec14_test_func.cpp`: funkcje bazowe i `sr_func`](https://raw.githubusercontent.com/P-N-Suganthan/CEC2014/98488087d590c29aaded9978ccfe2a356d10dd63/cec14-c-code.zip).

### Hybrydy F17–F22

Hybryda najpierw oblicza `M @ (x-o)` dla całego wektora, następnie stosuje oficjalną permutację i dzieli wynik na grupy. Dla wszystkich grup poza ostatnią liczność wynosi `ceil(p_i*D)`; ostatnia dostaje pozostałe współrzędne. Jądra grup stosują własne skale i przesunięcia wewnętrzne, bez kolejnego przesunięcia instancji i bez kolejnej rotacji. Ta kolejność jest istotna: niezależne obracanie małych grup nie odtwarza tego samego problemu.

| F | Proporcje grup | Jądra w kolejności |
|---|---|---|
| 17 | .3, .3, .4 | Schwefel; Rastrigin; Elliptic |
| 18 | .3, .3, .4 | Bent Cigar; HGBat; Rastrigin |
| 19 | .2, .2, .3, .3 | Griewank; Weierstrass; Rosenbrock; Scaffer F6 |
| 20 | .2, .2, .3, .3 | HGBat; Discus; Griewank–Rosenbrock; Rastrigin |
| 21 | .1, .2, .2, .2, .3 | Scaffer F6; HGBat; Rosenbrock; Schwefel; Elliptic |
| 22 | .1, .2, .2, .2, .3 | Katsuura; HappyCat; Griewank–Rosenbrock; Schwefel; Ackley |

Źródłem tych parametrów są sekcje hybryd w raporcie i funkcje `hf01`–`hf06` w [oficjalnej dystrybucji](https://raw.githubusercontent.com/P-N-Suganthan/CEC2014/98488087d590c29aaded9978ccfe2a356d10dd63/cec14-c-code.zip). Domyślne D=30 i pozostałe trzy wspierane wymiary nie tworzą pustych grup.

### Kompozycje F23–F30

Każdy składnik ma własne oficjalne przesunięcie i macierz. Ten sam wektor przesunięcia jest środkiem używanym do obliczenia jego wagi. Waga przed normalizacją to

`w_i = exp(-||x-o_i||² / (2*D*sigma_i²)) / sqrt(||x-o_i||²)`.

Przy dokładnym trafieniu w środek oficjalne C używa skończonego `1e99`; pakiet zachowuje tę regułę. Jeśli wszystkie wagi zanikną numerycznie, są zastępowane równymi wagami. Wynik jest średnią ważoną przeskalowanych wartości składników z biasami `0,100,200,…`, a dopiero na końcu dodawany jest zewnętrzny bias `100*F`.

Poniższe parametry odpowiadają tablicy `_COMPOSITIONS` i funkcjom `cf01`–`cf06` oficjalnego C. λ oznacza matematyczny mnożnik składnika; implementacja zachowuje kolejność `licznik * wartość / mianownik` z C, aby ograniczyć dodatkowe różnice zaokrągleń.

| F | Jądra | λ | sigma |
|---|---|---|---|
| 23 | Rosenbrock, Elliptic, Bent Cigar, Discus, Elliptic | 1, 1e−6, 1e−26, 1e−6, 1e−6 | 10,20,30,40,50 |
| 24 | Schwefel, Rastrigin, HGBat | 1,1,1 | 20,20,20 |
| 25 | Schwefel, Rastrigin, Elliptic | .25,1,1e−7 | 10,30,50 |
| 26 | Schwefel, HappyCat, Elliptic, Weierstrass, Griewank | .25,1,1e−7,2.5,10 | 10,10,10,10,10 |
| 27 | HGBat, Rastrigin, Schwefel, Weierstrass, Elliptic | 10,10,2.5,25,1e−6 | 10,10,10,20,20 |
| 28 | Griewank–Rosenbrock, HappyCat, Schwefel, Scaffer F6, Elliptic | 2.5,10,2.5,.0005,1e−6 | 10,20,30,40,50 |

Piąty składnik F23 oraz pierwszy składnik F24 są bez rotacji zgodnie z C. W F29 składnikami są hybrydy F17–F19 bez ich zewnętrznych biasów; w F30 analogicznie F20–F22. Obie kompozycje mają sigma `10,30,50` i korzystają z trzech zestawów danych należących do F29/F30. Wywołanie oddzielnej instancji publicznej F17 w środku F29 byłoby błędne, ponieważ użyłoby innych przesunięć, macierzy i permutacji. [Oficjalne C: `cf01`–`cf08`, `cf_cal`](https://raw.githubusercontent.com/P-N-Suganthan/CEC2014/98488087d590c29aaded9978ccfe2a356d10dd63/cec14-c-code.zip).

### Rozbieżności i decyzje implementacyjne

| Miejsce | Rozbieżność / ryzyko | Zachowanie pakietu |
|---|---|---|
| Instancje CEC | Wcześniejszy kod generował własne przesunięcia i rotacje | Oficjalne dane ze wskazanego archiwum; stare instancje nadal pod `cNN_` |
| HappyCat F13, HGBat F14 | Równania 27/28 nie pokazują wewnętrznego −1 obecnego w C | Wewnętrzne −1; w oficjalnym przesunięciu otrzymujemy bias |
| Scaffer F6 F16 | Równanie 30 drukowanego raportu pokazuje +1, którego nie ma w C | Brak +1, zgodnie z programem referencyjnym |
| Kompozycja F23 | Bardzo mały mnożnik Bent Cigar może wyglądać na literówkę | Zachowane 1e−26; nie zastąpione arbitralnym większym mnożnikiem |
| F29/F30 | Oddzielne hybrydy mogą przypadkowo używać innych środków niż wagi | Wspólne dane każdego składnika kompozycji i jego wagi |
| Błędne wejście | Zamiana NaN na inf może ukrywać problem operatora lub danych | Jawny wyjątek przy NaN/inf, złym kształcie lub domenie |
| Wymiary | Dowolny wymiar wymagałby nowych danych instancji | Jawna lista 10,30,50,100; brak generowania D=200 |

Numery równań odnoszą się do oryginalnego raportu, odpowiednio fizyczne strony PDF 14–16. Wspólnym sprawdzeniem decyzji numerycznych są punkty referencyjne obliczone przez C oraz wszystkie 120 oficjalnych przesuniętych optimów. Nie oznacza to, że każda drukowana formuła została przepisana dosłownie. [Oryginalny raport](https://github.com/P-N-Suganthan/CEC2014/blob/98488087d590c29aaded9978ccfe2a356d10dd63/Definitions%20of%20%20CEC2014%20benchmark%20suite%20Part%20A.pdf).

## Katalog binarny: 10 zachowanych funkcji

Poniższe definicje opisują dokładnie funkcje zaimplementowane w `discrete.py`. Wszystkie mają dziedzinę `{0,1}^n` i są minimalizowane. Są zgodne z poprzednimi `d01`–`d10` dla poprawnych wymiarów. Indeksy w poniższych wzorach zaczynają się od 0; sąsiedztwo modulo n dotyczy NK i cyklu MaxCut, a autokorelacja LABS jest aperiodyczna.

| ID w kodzie | Minimalizowana funkcja | Ograniczenie n | Znane optimum |
|---|---|---|---|
| `b01_labs_binary` | `−n²/(2E)`, `E=sum(k=1..n−1) C_k²`, `C_k=sum(i=0..n−k−1) s_i*s_(i+k)`, `s_i=2*x_i−1` | n≥2 | Nie deklarowane ogólnie |
| `b02_trap5` | Ujemna suma trapów długości 5 | n dodatnie, podzielne przez 5 | −n |
| `b03_nk_k4` | `−(1/n)*sum(i=0..n−1) T_i[x_i,…,x_(i+4)]` | n≥5 | Nie deklarowane dla losowej instancji |
| `b04_onemax` | `−sum(x_i)` | n≥1 | −n |
| `b05_zeromax` | `−sum(1−x_i)` | n≥1 | −n |
| `b06_leading_ones` | Minus długość początkowego ciągu jedynek | n≥1 | −n |
| `b07_alternating_bits` | Minus lepsza liczba zgodnych bitów z `1010…` lub `0101…` | n≥1 | −n |
| `b08_trap4` | Ujemna suma trapów długości 4 | n dodatnie, podzielne przez 4 | −n |
| `b09_royal_road4` | `−4` razy liczba pełnych bloków `1111` | n dodatnie, podzielne przez 4 | −n |
| `b10_maxcut_ring` | `−sum(i=0..n−1) [x_i != x_((i+1) mod n)]` | n≥3 | `−(n−n%2)` |

Dla Trap-k wynik dodatni pojedynczego bloku o u jedynkach wynosi k, gdy u=k, a w pozostałych przypadkach `k−1−u`. Projekt używa tej skali całkowitoliczbowej. Opis IOH PBO F24 dzieli wynik bloku przez k; jest to dodatnie przeskalowanie tego samego krajobrazu, ale nie ten sam zapisany fitness. Pakiet zachowuje poprzednią skalę IslandsEA. Definicje OneMax, LeadingOnes i merit factor LABS można porównać z [oficjalnym opisem IOH PBO, F1/F2/F18/F24](https://iohprofiler.github.io/IOHproblem/PBO).

LABS zachowuje **ujemny merit factor**, a nie dodatnią energię E. Obie reprezentacje prowadzą do tych samych rozwiązań optymalnych przy stałym n, ale zmieniają wartości i skalę poprawy rejestrowane w logach. Dla n≥2 ostatnia autokorelacja ma kwadrat 1, więc mianownik nie jest zerowy. Obliczenia wykorzystują liczby ze znakiem, aby `2*x−1` nie uległo zawinięciu w typie bez znaku.

NK zachowuje K=4 i sąsiedztwo cykliczne `i,i+1,…,i+4`, a nie losową macierz sąsiedztwa. Domyślne tablice mają n wierszy po 32 wartości, generowane przez `random.Random(20260511).random()` w kolejności wierszowej. Bit `x_i` jest najbardziej znaczącym bitem indeksu. Wynik jest sumowany w tej samej kolejności co w starszym kodzie. Manifest zapisuje całe tablice, aby odtworzenie instancji nie zależało wyłącznie od zapamiętania seeda. Dla porównania IOH PBO F25 stosuje K=1 i inne sąsiedztwo; nie należy utożsamiać tych instancji. [Kod NK w IOHexperimenter](https://raw.githubusercontent.com/IOHprofiler/IOHexperimenter/master/include/ioh/problem/pbo/nk_landscapes.hpp).

RoyalRoad4 jest prostym wariantem blokowym typu R1, z blokami długości 4 i bez dodatkowych nagród za hierarchie większych bloków. Jest zgodny z dotychczasową funkcją projektu. Oryginalna praca Mitchell, Forrest i Hollanda omawia także rozbudowane hierarchie schematów i eksperymenty dla ciągów 64-bitowych; nasz wariant nie odtwarza wszystkich tych konstrukcji. [Mitchell, Forrest, Holland, 1992, sekcje 3–4](https://www.melaniemitchell.me/PapersContent/ecal92.pdf).

MaxCut na cyklu ma n przeciętych krawędzi dla n parzystego i najwyżej n−1 dla nieparzystego. Wynika to z naprzemienności kolorów przy przejściu po zamkniętym cyklu; parzysta liczba zmian jest konieczna do powrotu do koloru początkowego. To szczególny, łatwo rozwiązywalny przypadek MaxCut. AlternatingBits jest osobną funkcją zgodności bitowej, a nie liczbą przeciętych krawędzi, mimo wspólnych naprzemiennych optimów przy n parzystym.

Zestaw zawiera problemy o powiązanej strukturze: OneMax i ZeroMax są symetryczne przez zamianę bitów, a Trap4/Trap5 należą do jednej rodziny. Zachowanie dziesięciu istniejących funkcji pozwala kontynuować obecny zakres badań, lecz nie daje podstaw do opisywania ich jako dziesięciu niezależnych rodzin trudności. Dla LABS i NK `optimum_value=None` zapobiega raportowaniu błędu względem nieudowodnionego optimum.

## Walidacja i jej zakres

Wyniki maszynowe zapisano w `validation_report.json`; dokładne asercje znajdują się w `tests/`. Testy odniesienia nie korzystają z wyniku obliczonego przez tę samą implementację Pythona jako oczekiwanej wartości.

| Sprawdzenie | Zakres | Wynik lokalny |
|---|---|---|
| Oficjalny program C | 1776 punktów, wszystkie 30×4 instancje | Zgodne przy `rel_tol=1e−10`, `abs_tol=1e−8` |
| Oficjalne globalne optima | Pierwszy wektor przesunięcia dla każdej z 120 instancji | Błąd bezwzględny ≤1e−8 względem biasu |
| Dziedziny wejść | Błędne długości, wymiary, typy, NaN/inf, punkty poza granicami, niebinarne wartości | Jawne odrzucenie |
| Funkcje binarne, małe n | Pełny przegląd bitstringów, niezależne proste wzory referencyjne | Zgodne |
| Funkcje binarne, większe n | Długości 60,100,200, deterministyczne punkty losowe | Zgodne |
| Regresja wobec starej binarnej fabryki | 20 losowych ciągów × 10 funkcji, n=60 | Identyczne wartości float |
| Adaptery i operatory jMetalPy | Wszystkie 40 funkcji; 8 osobników, 4 potomków, 24 ewaluacje | Pełne krótkie przebiegi zakończone |
| Serializacja | `pickle` każdego z 40 adapterów i ponowna ewaluacja | Zachowana wartość |
| Aktywna fabryka i algorytm wyspowy | F29 i NK; prawdziwy pierwszy krok GA; lokalne zastępstwo komunikacji jednej wyspy | Poprawny krok i manifest zgodny z parametrami |

1776 punktów referencyjnych obejmuje zero, oba końce przedziału, rampę, punkt blisko optimum, każdy używany środek kompozycji oraz osiem deterministycznych punktów losowych na funkcję i wymiar. Są to kontrole wartości poza optimum, potrzebne do wykrywania błędnej skali, orientacji macierzy i wag. Sam test wartości w optimum byłby za słaby: wiele niezgodnych transformacji także zeruje się w wybranym środku.

Oficjalny C został skompilowany z MSVC x64 z `/O2 /fp:precise`. Jedynymi poprawkami źródła są usunięcie nieużywanego `WINDOWS.H` i zamiana formatu wejściowego `%Lf` na `%lf` przy odczycie do `double*`. Generator zapisuje komendę kompilacji, hash oryginalnego C i pochodzenie archiwum wraz z wektorami. Obsługuje także g++ z `-O2 -fno-fast-math`, ale dołączone wyniki odniesienia pochodzą z wykonanej kompilacji MSVC.

Pełny lokalny wynik to **13 testów, 0 błędów, 0 niepowodzeń i 0 pominięć**, w środowisku Windows 11, Python 3.12.14, NumPy 1.26.4, jMetalPy 1.5.5, Ray 2.31.0, SciPy 1.14.1 i scikit-learn 1.5.2. Testy są krótkie i można je powtórzyć przez `python -m islands_desync.geneticAlgorithm.utils.benchmarks_refined --validate`. Wariant `--core-only` ma 9 testów i nie obejmuje integracji z GA.

Walidacja nie stanowi dowodu równości funkcji w każdym rzeczywistym punkcie ani gwarancji identyczności bitowej przy innym BLAS. Nie obejmuje uruchomienia Aresa/SLURM, rozproszonej migracji ani wyników statystycznych optymalizatora. Weryfikacja na docelowym Pythonie 3.10 i stosie Aresa jest osobnym etapem środowiskowym. Kod testów, dane oraz instrukcja uruchomienia są już dołączone, więc nie wymaga to ponownego pobierania benchmarków.

## Konsekwencje dla eksperymentów IslandsEA

Oficjalny protokół CEC określa 51 powtórzeń, budżet `10000*D`, wymiary 10/30/50/100 i raportowanie błędu względem optimum. Projektowy `zakres_badan.pdf` opisuje badanie modelu wyspowego z własnymi parametrami, m.in. budżetem 8000 ewaluacji na wyspę, populacją 16, czterema potomkami i trzema powtórzeniami. Użycie zgodnych funkcji CEC w takim eksperymencie jest zasadne, ale sam eksperyment nie jest powtórzeniem oficjalnego protokołu konkursowego. [Raport CEC, sekcja 2, fizyczna strona 27](https://github.com/P-N-Suganthan/CEC2014/blob/98488087d590c29aaded9978ccfe2a356d10dd63/Definitions%20of%20%20CEC2014%20benchmark%20suite%20Part%20A.pdf); lokalny `zakres_badan.pdf` w katalogu nadrzędnym workspace.

W CEC do porównania jakości na danej funkcji należy używać `f(x)-100*F`, zachowując surowe fitness w logach. Średnia surowych wartości z różnych funkcji miesza różne biasy i skale. Także błędy po odjęciu biasu mają różne skale; porównania zbiorcze wymagają jawnej metody, np. rankingów wewnątrz każdej funkcji. Dla binarnych funkcji ze znanym optimum można obliczać lukę; dla LABS i NK trzeba operować wynikiem celu lub osobno udokumentowanym punktem odniesienia.

Poprawiony kod ma inne koszty ewaluacji niż poprzedni. Rotacje kosztują kwadratowo względem D, LABS w obecnym prostym wariancie kwadratowo względem n, a funkcje blokowe i NK przy stałym K liniowo. Różnice czasu liczenia należą do kontekstu badań asynchronicznych i mogą wpływać na obserwowane opóźnienia. Porównania topologii i strategii wymagają tej samej wersji funkcji, instancji, wymiaru i konfiguracji środowiska w danej grupie. Nie należy traktować wyników `cNN_` i `rNN_` jako powtórzeń tej samej instancji CEC.

Pakiet zachowuje dotychczasowy mechanizm migracji i znaki opóźnień. Integracja dodaje wybór nowych problemów i manifest instancji, zapisany przed pętlą ewolucji. Test pierwszego kroku sprawdza współpracę z aktywną fabryką, lecz nie zamyka znanych w `AGENTS.md` kwestii topologii i skryptów SLURM. Te elementy pozostają częścią oddzielnej walidacji eksperymentu rozproszonego.

## Źródła i artefakty kontrolne

1. J. J. Liang, B. Y. Qu, P. N. Suganthan. [Problem Definitions and Evaluation Criteria for the CEC 2014 Special Session and Competition on Single Objective Real-Parameter Numerical Optimization](https://github.com/P-N-Suganthan/CEC2014/blob/98488087d590c29aaded9978ccfe2a356d10dd63/Definitions%20of%20%20CEC2014%20benchmark%20suite%20Part%20A.pdf). Technical Report 201311, grudzień 2013. Definicje F1–F30 i protokół konkursu; lokalna transkrypcja Markdown dostarczona w projekcie.
2. J. J. Liang / repozytorium P. N. Suganthana. [CEC14 Test Function Suite — oficjalne archiwum C](https://raw.githubusercontent.com/P-N-Suganthan/CEC2014/98488087d590c29aaded9978ccfe2a356d10dd63/cec14-c-code.zip), grudzień 2013, commit przypięty powyżej. Referencyjne wzory wykonawcze i dane instancji.
3. IOHprofiler. [Pseudo-Boolean Optimization Problem Set](https://iohprofiler.github.io/IOHproblem/PBO). Definicje OneMax, LeadingOnes, LABS, normalizowanego Concatenated Trap i opis parametryzacji NK. Strona odwołuje się do C. Doerr et al., *Benchmarking discrete optimization heuristics with IOHprofiler*, Applied Soft Computing 88, 106027, 2020.
4. IOHexperimenter. [Źródło `nk_landscapes.hpp`](https://raw.githubusercontent.com/IOHprofiler/IOHexperimenter/master/include/ioh/problem/pbo/nk_landscapes.hpp). Pomocnicze porównanie mechanizmu instancji NK; nie jest generatorem użytym w tym pakiecie.
5. M. Mitchell, S. Forrest, J. H. Holland. [The Royal Road for Genetic Algorithms: Fitness Landscapes and GA Performance](https://www.melaniemitchell.me/PapersContent/ecal92.pdf). Proceedings of the First European Conference on Artificial Life, MIT Press, 1992. Rodzina Royal Road i warianty hierarchiczne.
6. NumPy. [Global Configuration Options](https://numpy.org/doc/stable/reference/global_state.html). Ustawienia wielowątkowości bibliotek BLAS, wykorzystane w instrukcji uruchomienia.
7. IslandsEA, lokalny kod `geneticAlgorithm/utils/benchmark_problems.py`: historyczny rejestr `c01`–`c30`, `d01`–`d10` oraz definicje binarne. Lokalny `AGENTS.md` i `zakres_badan.pdf`: zakres badań, zasady porównywalności i kontekst HPC.
8. Artefakty pakietu: [manifest danych](data/manifest.json), [wynik walidacji](validation_report.json), [testy CEC](tests/test_cec2014.py), [testy binarne](tests/test_discrete.py), [testy integracji](tests/test_integration.py), [generator oficjalnego odniesienia](tools/generate_cec_reference.py).
