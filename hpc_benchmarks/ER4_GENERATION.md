# ER4 dla 144 wysp - zatwierdzona generacja

Aktualizacja 2026-09-17 na podstawie odpowiedzi Sylwii Biełaszek przekazanej
przez użytkownika. Zgoda zastępuje wcześniejszy obowiązek użycia starego
załącznika ER4 na 150 węzłów. Nie dotyczy zmian w WS3 ani BA.

## Ustalenia i sposób wykonania

- Biblioteka **igraph**, model **G(n,p)**, `n=144`, `p=0.0347`.
- Graf **nieskierowany**; losowanie bez pętli: `directed=False, loops=False`.
- Po losowaniu dodajemy dokładnie jedną pętlę wyłącznie do każdego węzła
  bez sąsiadów. Węzłom z sąsiadami nie dodajemy pętli. Pętla daje izolowanej
  wyspie cel migracji, ale nie łączy jej z innymi wyspami.
- W mailu wskazano preferencję najwyżej 2-3 węzłów odłączonych od dużej
  składowej. Przyjęty jawny warunek: **najwyżej 3 węzły poza największą
  składową**, czyli jej rozmiar co najmniej 141. Jest to kontrola mocniejsza
  niż samo liczenie izolowanych węzłów; uwzględnia też małe osobne składowe.
- Nie wymagamy pełnej spójności, nie łączymy składowych sztucznymi krawędziami
  i nie zmieniamy p. Kandydaci są losowani dla seedów 20260917, 20260918,…;
  bierzemy **pierwszego** spełniającego warunek. Limit 10000 prób kończy się
  błędem, bez zapisania zastępczego grafu. To jawny wybór warunkowany
  spójnością, a nie przeszukiwanie pod wynik GA czy wzorzec opóźnień.
- Seed generatora ustalono przed obejrzeniem pierwszego kandydata.
  Nie zależy od seedu/repeatu algorytmu ewolucyjnego.

Wywołanie generatora odpowiada [oficjalnej dokumentacji igraph](https://python.igraph.org/en/0.11.9/tutorials/erdos_renyi.html).
RNG jest jawnie przekazywany przez
`igraph.set_random_number_generator(random.Random(seed))`.

## Zamrożona instancja

| Pole | Wartość |
|---|---|
| Nazwa CLI / instancji | `er4` / `er4-144-p00347-v1` |
| Wybrany seed / numer próby | **20260917 / 1** |
| Węzły | **144**, identyfikatory 0-143 |
| Krawędzie nieskierowane bez pętli | **365** |
| Wpisy na listach sąsiadów | **730** (dwa wpisy na krawędź) |
| Rozmiary składowych | **[144]** |
| Poza największą składową | **0** |
| Izolowane węzły / dodane pętle | **0 / 0** |
| Python / igraph / rdzeń C igraph | **3.12.14 / 0.11.9 / 0.10.16** |
| SHA-256 kanonicznej adjacencji | `469cc283543dcc60d5bf8f07db2eabfb12cab34637f4a6d26bca51d07f85cccc` |

Pełna spójność jest wynikiem pierwszego losowania; nie wymuszano jej przez
kolejne próby. Zero izolowanych węzłów spełnia warunek „nie więcej niż 2–3”.
Nie dodajemy izolowanych wysp ani pętli, aby naśladować średnią 148,166 z badań
przy 150 węzłach - ta średnia jest informacją porównawczą, a nie celem generacji.

Oba repozytoria zawierają **identyczny plik**
`islands_desync/islands_desync/islands/topologies/data/er4.json`.
Jeden graf obowiązuje wszystkie powtórzenia, benchmarki i strategie na CPU/GPU.
Listy nowej instancji uporządkowano raz rosnąco; runtime zachowuje ich kolejność.
Parametry, seed, wersje, historia prób, statystyki i hashe generatora/grafu są
w proweniencji JSON oraz trafiają do parametrów topologii w manifestach runów.

Stary graf 150 zachowano bez zmian jako
`data/archive/er4_legacy150.json`; oryginalny plik workspace
`grafy/ER4Topology.py` jest archiwalnym załącznikiem. Nowy graf nie jest jego
obcięciem ani symetryzacją. Historycznych wyników dla starej instancji nie
należy mieszać z nowymi; rozróżnia je hash grafu i pełne metadane.

## Odtworzenie offline

`igraph` **nie jest zależnością uruchomień HPC**. Runtime wczytuje gotowy JSON
i sprawdza go czystym Pythonem w `er4_contract.py`/`fixed_graph.py`.
Generator służy przygotowaniu/odtworzeniu danych w osobnym lokalnym środowisku.
Do dokładnego odtworzenia całego JSON-u użyj zapisanych wyżej wersji, w tym
Pythona 3.12.14, i zależności `requirements-graphs.txt`:

```bash
# W osobnym środowisku do odtwarzania, z katalogu repozytorium:
python -m pip install -r hpc_benchmarks/requirements-graphs.txt
python hpc_benchmarks/generate_er4.py --check
# Alternatywnie zapisz nowy plik do porównania; istniejący plik nie jest nadpisywany:
python hpc_benchmarks/generate_er4.py --output /sciezka/do/nowego/er4.json
```

`--check` porównuje cały odtworzony dokument z instancją produkcyjną.
Sam seed bez wersji generatora nie zastępuje zapisu dokładnego grafu.
Nie regenerować grafu przy starcie joba ani zmieniać seedu w celu uzyskania
lepszego wyniku eksperymentu.

## Walidacja i uruchamianie

```bash
python -m unittest discover -s hpc_benchmarks -p test_study_topologies.py
python -m unittest discover -s hpc_benchmarks -p test_er4_contract.py
python hpc_benchmarks/run_benchmark.py --problem r01_elliptic --dimension 200 --topology er4 --dry-run
```

W repo Atheny dodatkowo:

```bash
python athena_gpu/run_study.py --problem r01_elliptic --dimension 200 --topology er4 --dry-run
```

Preflight nie uruchamia Ray ani GPU. Jawna stara blokada ER4 w runnerze Atheny
została usunięta; oba runnery używają tego samego zweryfikowanego grafu.
Testy obejmują odtworzenie i hash, symetrię, brak duplikatów, mapowanie aktorów,
regułę 0–3 izolowanych węzłów, odrzucenie ponad 3 węzłów poza największą składową
(także gdy tworzą osobny cykl), błędne pętle i ograniczenie prób generatora.
Odblokowanie ER4 nie znosi pozostałych kontroli środowiska, commita, canary,
budżetu ani konieczności walidacji na docelowym GPU. W tej aktualizacji nie
wysyłano żadnych zadań HPC.
