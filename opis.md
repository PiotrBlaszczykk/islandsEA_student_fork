# Opis wyników analizy

## Wykresy opóźnień migracji

### Cel

Wykresy pokazują typowe zmiany opóźnień migracji w czasie działania algorytmu.
Analizę wykonujemy osobno dla 10 najlepszych i 10 najgorszych wysp z każdego
runu. Możemy połączyć wszystkie benchmarki albo przygotować osobne wzory dla
każdego benchmarku.

Do grupowania używamy algorytmu **K-Means**. Wybieramy 8 największych klastrów jako reprezentatywne wzory opóźnień.

### 1. Obliczenie opóźnienia

Dla każdej przetworzonej migracji zapisujemy krok źródłowej wyspy w momencie
wysłania migranta oraz krok wyspy docelowej w momencie jego odebrania.
Opóźnienie jest zdefiniowane jako

$$
d_j = s_j^{\mathrm{source}} - s_j^{\mathrm{destination}}.
$$

Interpretacja znaku:

- $d_j < 0$ — migrant jest opóźniony, ponieważ wyspa docelowa zdążyła wykonać
  więcej kroków;
- $d_j = 0$ — obie wyspy są na tym samym etapie;
- $d_j > 0$ — wyspa źródłowa była bardziej zaawansowana od docelowej.

Migracje, które nie zostały przetworzone przed końcem runu, są pomijane, bo nie
mają obserwowalnego opóźnienia.

### 2. Wybór wysp

Po zakończeniu runu porządkujemy wyspy według końcowego fitnessu, uwzględniając
kierunek optymalizacji. Następnie wybieramy:

- 10 wysp z najlepszym wynikiem — grupa `top_10`;
- 10 wysp z najgorszym wynikiem — grupa `bottom_10`.

Obie grupy są analizowane i klastrowane niezależnie.

### 3. Podział czasu na przedziały

Runy mogą mieć różną liczbę zdarzeń, dlatego oś czasu każdej wyspy normalizujemy
i dzielimy na $K=100$ równych przedziałów. Dla kroku odbiorcy $t_j$ i maksymalnej
liczby kroków $T_i$ indeks przedziału wynosi

$$
k_j = \min\left(K-1,\left\lfloor
K\cdot\min\left(1,\max\left(0,\frac{t_j}{T_i}\right)\right)
\right\rfloor\right).
$$

Zbiór opóźnień wyspy $i$ wpadających do przedziału $k$ oznaczamy jako
$M_{ik}$.

### 4. Cechy opisujące kształt przebiegu

W każdym niepustym przedziale obliczamy średnią, odchylenie standardowe,
minimum, maksimum oraz informację, czy w przedziale wystąpiła migracja:

$$
\mu_{ik}=\frac{1}{|M_{ik}|}\sum_{d\in M_{ik}}d,
$$

$$
\sigma_{ik}=\sqrt{\max\left(
\frac{1}{|M_{ik}|}\sum_{d\in M_{ik}}d^2-\mu_{ik}^2,\,0
\right)},
$$

$$
m_{ik}^{\min}=\min_{d\in M_{ik}}d,
\qquad
m_{ik}^{\max}=\max_{d\in M_{ik}}d,
$$

$$
c_{ik}=\mathbb{1}[|M_{ik}|>0].
$$

Brakujące przedziały uzupełniamy interpolacją liniową. Następnie cztery kanały
opóźnienia wygładzamy średnią ruchomą o nieparzystym oknie $W=5$:

$$
\widetilde{x}_{ik}=\frac{1}{W}
\sum_{r=-\lfloor W/2\rfloor}^{\lfloor W/2\rfloor}x_{i,k+r}.
$$

Na brzegach powtarzamy najbliższą dostępną wartość.

### 5. Normalizacja

Chcemy porównywać przede wszystkim kształt przebiegów, a nie tylko ich
bezwzględną amplitudę. Dla każdej wyspy wyznaczamy skalę

$$
a_i=\max\left(
Q_{0.90}\left(
|\widetilde{\mu}_i|,\widetilde{\sigma}_i,
|\widetilde{m}^{\min}_i|,|\widetilde{m}^{\max}_i|
\right),10^{-12}
\right),
$$

gdzie $Q_{0.90}$ oznacza wspólny 90. percentyl wartości czterech kanałów.
Wektor cech wyspy ma postać

$$
\mathbf{x}_i=
\left[
\operatorname{clip}\left(\frac{\widetilde{\mu}_i}{a_i},-4,4\right),
\operatorname{clip}\left(\frac{\widetilde{\sigma}_i}{a_i},-4,4\right),
\operatorname{clip}\left(\frac{\widetilde{m}^{\min}_i}{a_i},-4,4\right),
\operatorname{clip}\left(\frac{\widetilde{m}^{\max}_i}{a_i},-4,4\right),
1.5\,c_i
\right].
$$

Kanał $c_i$ pozwala odróżnić rzeczywiście obserwowane fragmenty przebiegu od
fragmentów uzupełnionych interpolacją.

### 6. Grupowanie K-Means

Osobno dla grup `top_10` i `bottom_10` uruchamiamy K-Means z 12 klastrami.
Algorytm minimalizuje sumę kwadratów odległości przebiegów od środków klastrów:

$$
\min_{C_1,\ldots,C_L}
\sum_{\ell=1}^{L}\sum_{\mathbf{x}_i\in C_\ell}
\left\|\mathbf{x}_i-\boldsymbol{\mu}_\ell\right\|_2^2,
\qquad L=12.
$$

Dla powtarzalności używamy stałego ziarna losowego, `n_init=20` oraz
`max_iter=500`. Klastry sortujemy według liczby przypisanych przebiegów i
wybieramy 8 najczęstszych wzorów.

### 7. Wizualizacja PCA 2D

Dla grup `top_10` i `bottom_10` tworzymy osobne wykresy
`pca_clusters.png`. PCA rzutuje dokładnie te same wektory cech
$\mathbf{x}_i$, które zostały przekazane do K-Means, na dwie osie:

$$
\mathbf{z}_i=(\mathbf{x}_i-\overline{\mathbf{x}})\mathbf{W}_2,
$$

gdzie kolumny $\mathbf{W}_2$ są dwoma najważniejszymi kierunkami PCA. Udział
zmienności wyjaśnionej przez oś $j$ wynosi

$$
r_j=\frac{\lambda_j}{\sum_k\lambda_k}.
$$

Każdy punkt oznacza przebieg jednej wyspy w jednym runie. Kolor pochodzi z
przypisania K-Means, a znak `X` wskazuje rzeczywisty przebieg wybrany jako
reprezentant klastra. PCA służy wyłącznie do wizualizacji i nie zmienia
klastrów. Obraz powstaje dla raportu globalnego, per benchmark i dla
pojedynczego runu.

### 8. Wybór reprezentanta i utworzenie PNG

Nie rysujemy sztucznego środka klastra. Wybieramy rzeczywisty przebieg położony
najbliżej środka klastra:

$$
i_\ell^*=\arg\min_{i\in C_\ell}
\left\|\mathbf{x}_i-\boldsymbol{\mu}_\ell\right\|_2^2.
$$

Na wynikowym wykresie pokazujemy:

- wszystkie surowe, przetworzone opóźnienia reprezentanta względem kroku wyspy
  docelowej;
- wygładzoną średnią opóźnienia w kolejnych przedziałach czasu;
- poziomą linię $d=0$, która oddziela migracje opóźnione od przyspieszonych.

Każdy z 8 najczęstszych wzorów jest zapisywany jako osobny plik PNG. Dla trybu
per benchmark wyniki trafiają do `outputs/<benchmark>/top_10/` oraz
`outputs/<benchmark>/bottom_10/`.

### 9. Uruchomienie dla pojedynczego runu

```bash
./.venv/bin/python analysis/build_results_database.py \
  --output analysis_database \
  --plot-delay-patterns \
  --pattern-run RUN_ID
```

Domyślnie wynik trafia do `outputs/runs/<RUN_ID>/`.

## Struktura katalogu `outputs/`

Standardowy układ wyników wygląda następująco:

```text
outputs/
├── <benchmark>/
│   ├── fitness_summary.csv
│   ├── by_strategy/
│   │   ├── strategy_best.png
│   │   ├── strategy_maxDistance.png
│   │   └── strategy_random.png
│   ├── by_topology/
│   │   ├── topology_ba.png
│   │   ├── topology_complete.png
│   │   └── ...
│   ├── combined/
│   │   └── all_topology_strategy_configurations.png
│   ├── top_10/
│   │   ├── pca_clusters.png
│   │   ├── pattern_01.png
│   │   └── ... pattern_08.png
│   └── bottom_10/
│       ├── pca_clusters.png
│       ├── pattern_01.png
│       └── ... pattern_08.png
├── runs/
│   └── <RUN_ID>/
│       ├── top_10/
│       └── bottom_10/
└── delay_plots/
    ├── top_10/
    └── bottom_10/
```

Znaczenie katalogów i plików:

- `<benchmark>/` — komplet wyników dotyczących jednego benchmarku, na przykład
  `b01_labs_binary/` albo `r01_elliptic/`;
- `by_strategy/` — osobny wykres dla każdej strategii wyboru migrantów; linie
  na wykresie odpowiadają topologiom;
- `by_topology/` — osobny wykres dla każdej topologii; linie odpowiadają
  strategiom wyboru migrantów;
- `combined/` — wszystkie konfiguracje `topologia / strategia` na jednym
  wykresie;
- `top_10/` i `bottom_10/` — wzory opóźnień odpowiednio dla najlepszych i
  najgorszych wysp; każdy zawiera również `pca_clusters.png`;
- `runs/<RUN_ID>/` — raport ograniczony do pojedynczego runu;
- `delay_plots/` — wspólna agregacja wzorów opóźnień utworzona po połączeniu
  danych ze wszystkich benchmarków.
- `<benchmark>/top_10/` i `<benchmark>/bottom_10/` — wzory opóźnień utworzone
  wyłącznie na podstawie runów danego benchmarku.

## Legenda `fitness_summary.csv`

Każdy wiersz opisuje jedną konfigurację eksperymentu dla danego benchmarku z wynikiem uśrednionym ze wszystkich powtórzeń.

| Kolumna | Znaczenie |
|---|---|
| `dimension` | Liczba zmiennych problemu; dla problemów binarnych jest to liczba bitów. |
| `topology` | Topologia połączeń między wyspami, np. `torus`, `complete`, `er4`, `ws3` lub `ba`. |
| `migrant_selection` | Sposób wyboru osobników wysyłanych do innych wysp: `best`, `random` albo `maxDistance`. |
| `migrant_acceptance` | Strategia przyjmowania migrantów przez wyspę docelową, np. bazowe `plain`. |
| `objective_direction` | Kierunek optymalizacji: `minimize` albo `maximize`. Informuje, czy lepsza jest mniejsza, czy większa wartość fitnessu. |
| `repeats_averaged` | Liczba runów użytych do obliczenia średnich. W pełnym eksperymencie oczekiwana wartość to 3. |
| `evaluations_budget_per_island` | Maksymalna liczba ewaluacji przypadająca na jedną wyspę. |
| `mean_initial_best_fitness` | Średni najlepszy fitness dostępny na początku runu, po utworzeniu populacji początkowych. |
| `mean_best_fitness_at_25pct_evaluations` | Średni najlepszy dotychczas fitness po wykorzystaniu 25% budżetu ewaluacji. |
| `mean_best_fitness_at_50pct_evaluations` | Średni najlepszy dotychczas fitness po wykorzystaniu 50% budżetu. |
| `mean_best_fitness_at_75pct_evaluations` | Średni najlepszy dotychczas fitness po wykorzystaniu 75% budżetu. |
| `mean_best_fitness_at_100pct_evaluations` | Średni najlepszy dotychczas fitness dokładnie na końcu budżetu ewaluacji. |
| `mean_final_fitness` | Średni końcowy najlepszy fitness zapisany przez run. Dla kompletnego runu powinien być zgodny z wartością przy 100% budżetu. |
| `mean_evaluations_to_50pct_observed_improvement` | Średnia liczba ewaluacji potrzebna do osiągnięcia 50% poprawy rzeczywiście zaobserwowanej między początkiem a końcem runu. |
| `mean_evaluations_to_90pct_observed_improvement` | Średnia liczba ewaluacji potrzebna do osiągnięcia 90% zaobserwowanej poprawy. |

Wartości fitnessu w punktach 25%, 50%, 75% i 100% są globalnym najlepszym
wynikiem znalezionym dotychczas przez dowolną wyspę w danym runie. Dla udziału
budżetu $q$ wybieramy ostatni zapisany punkt spełniający

$$
e \le qE,
$$

gdzie $e$ jest liczbą ewaluacji na wyspę, a $E$ pełnym budżetem ewaluacji na
wyspę. Nie wykorzystujemy punktów późniejszych niż zadany próg.

Dla minimalizacji postęp w chwili $e$ obliczamy jako

$$
p(e)=\frac{f_{\mathrm{initial}}-f_{\mathrm{best}}(e)}
{f_{\mathrm{initial}}-f_{\mathrm{final}}}.
$$

Dla maksymalizacji odwracamy kierunek różnic:

$$
p(e)=\frac{f_{\mathrm{best}}(e)-f_{\mathrm{initial}}}
{f_{\mathrm{final}}-f_{\mathrm{initial}}}.
$$

Kolumny `mean_evaluations_to_50pct_observed_improvement` i
`mean_evaluations_to_90pct_observed_improvement` podają pierwszy moment, w
którym odpowiednio $p(e)\ge 0.5$ albo $p(e)\ge 0.9$, a następnie średnią z
powtórzeń. Jest to poprawa względem wyniku końcowego faktycznie osiągniętego w
runie, a nie względem teoretycznego optimum benchmarku.
