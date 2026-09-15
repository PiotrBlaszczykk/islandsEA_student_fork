# Badania: 144 wyspy i wybrane grafy

Wytyczne z maila przekazanego 2026-09-15 zastępują zapis 150–200 wysp
z `zakres_badan.pdf`. Każda z pięciu topologii badawczych ma mieć **144 wyspy**.
Nie zmienia się 40 benchmarków (30 ciągłych + 10 binarnych), ich danych,
wymiarów (w tym projektowego D=200), operatorów ani definicji metryk.

| CLI | Graf | Stan |
|---|---|---|
| `torus` | 12×12, 144 węzły, 576 skierowanych wpisów | gotowy |
| `complete` | 144 węzły, 20592 skierowane wpisy, bez pętli | gotowy |
| `ws3` | dokładny WS3 z załącznika; 144 węzły, 1803 krawędzie nieskierowane | gotowy |
| `ba` | dokładny BA z załącznika; m0=30, m=30, 144 węzły, 3855 krawędzi nieskierowanych | gotowy |
| `er4` | oryginał z załącznika: **150**, nie 144 węzły | blokada w preflight |

ER4: plik `ER4Topology.py` zawiera węzły 0–149, 728 skierowanych wpisów,
6 pętli własnych i niesymetryczne listy sąsiadów. To niezgodność załącznika
z zatwierdzoną liczebnością. **Nie obcięto** grafu, nie usunięto pętli,
nie symetryzowano go i nie wygenerowano zastępczego ER. Potrzebny jest
poprawiony graf 144 od prowadzącej albo jawna decyzja o konkretnej transformacji.
Nie uruchamiać ER4 z 150 wyspami w kampanii porównawczej. `probab` pozostaje
`null`, ponieważ nie podano go w załączniku (etykieta `ERt3.2`).

WS3 zachowuje parametry z etykiety źródła: dim=2, lat=12, nei=3,
probab=0.003181, scenario=2. Nie odtwarzamy grafów generatorem bibliotek:
wykorzystujemy dokładne, dostarczone listy sąsiadów, również ich kolejność,
która może wpływać na wybór celu migracji.

## Kontrakt obu implementacji

W `islands_desync/islands_desync/islands/topologies/data/` są identyczne JSON-y
`ws3.json`, `ba.json`, `er4.json`: listy sąsiadów, parametry, nazwa pliku źródłowego,
SHA-256 oryginalnego załącznika i kanonicznej adjacencji. `fixed_graph.py`
sprawdza integralność i dokładną liczebność; nie dokonuje losowania ani obcięcia.
`study.py` ustala 144 i pięć wybranych nazw. Parametry i proweniencja trafiają
do `topology.json`, `experiment_manifest.json` i `run_metadata.json`.
Launcher porównuje dane wybranych grafów na wszystkich węzłach przed GA.
`topology.png` jest obrazem pomocniczym; dokładne odtworzenie zapewnia JSON.

Domyślnie `run_benchmark.py` odrzuca inną liczbę wysp i stare ER1/ER2/ER3/WS4.
`ring` i małe uruchomienia są dostępne przez jawne `--diagnostic`, poza kampanią.
Tryb zapisuje się w konfiguracji naukowej; nie należy mieszać go z badaniami.
Legacy `start.py` używa tej samej listy topologii i sprawdza graf przed Ray.
Stare skrypty `run*-hpc.sh`, `run_delay_experiment.sh`, `run_local_venv_plgrid.sh`
oraz profile `*_ares_200.sh` są wyłączone i wskazują aktualny launcher.

Stałe badania: 8000 ewaluacji na wyspę (łącznie 1 152 000), populacja 16,
potomkowie 4, 5 migrantów, interwał 5 według dotychczasowego licznika ewaluacji.
Wybór migrantów: best/random/maxDistance; podstawowa akceptacja plain.
Macierz nadal wynosi 5×3×40×3 = 1800 runów, lecz ER4 pozostaje zablokowany.
Wszystkie wyniki wysp, `param.json`, dokładna topologia i obraz oraz pełne
`research-v1-full-buffered` są zachowane. Semantyka signed delay, kolejkowania,
filtrów, RNG i zapisu metryk nie została zmieniona.

## Ares (CPU)

Profil `hpc_benchmarks/submit_ares_144.sh`: **7×48 = 336 CPU**,
335 udostępnione Ray; potrzeba 144 Island + 144 Computation + SignalActor
= 289 CPU Ray oraz CPU drivera (minimum 290). Sześć węzłów po 48 nie wystarcza.
Grant/partycja: plglscclass26-cpu/plgrid. Standardowy walltime 30 minut.
Submitter sprawdza konfigurację przed `sbatch`; job ponawia kontrolę przed Ray.
Używać brancha `summer_benchmarks_ares`.

Bez uruchamiania klastra, w środowisku projektu:

```bash
python hpc_benchmarks/run_benchmark.py --problem r01_elliptic --dimension 200 --topology ba --dry-run
python hpc_benchmarks/run_benchmark.py --problem r01_elliptic --dimension 200 --topology ws3 --dry-run
python -m unittest discover -s hpc_benchmarks -p 'test_study_topologies.py'
python -m unittest pilot_run.test_pilot_tools
```

Pierwszy test infrastruktury, po przeniesieniu i zatwierdzeniu zmian w Git:

```bash
bash hpc_benchmarks/submit_ares_144.sh --problem r01_elliptic --dimension 200 --topology ba --evaluations 128 --strategy best --acceptance plain
```

Pilot F1/D200/best/plain: 144 wyspy, torus12×12, powtórzenia 1–3.
`pilot_run/pilot_spec.json` jest źródłem parametrów. Canary10min ≤56 CPUh,
3×pełny repeat30min ≤504 CPUh, gate≤0.5 CPUh, finalizer≤1 CPUh,
łącznie **≤561.5 CPUh**. Istniejący argument zgody kosztowej to teraz
`--confirm-144-and-562-cpuh`; nie ma już bramki metodologicznej CONFIRM_TORUS_200.
Wciąż wymagane są: czysty przypięty commit, SCRATCH, zaliczony canary,
kompletne wyniki i weryfikacja przez finalizer. Nie ma automatycznych retry.

## Athena (GPU)

Ten sam kontrakt 144/topologie i te same dane obowiązują GPU. Nie wolno
zmniejszać liczby wysp tylko z powodu alokacji GPU. Docelowo 2304 osobniki
inicjalne (144×16), 576 potomków na idealną falę (144×4), 1 152 000 ewaluacji.
To opis obciążenia, nie dodatkowa bariera synchronizacji między wyspami.
Walidator batchy uwzględnia rozmiary 144,288,576,864,1152,1728,2304.

**Pełny GPU runner wysp nadal nie jest zaimplementowany**. Dostępny jest
batch CPU/CuPy dla 40 funkcji i testy A100, a kod GA/Ray w repo pozostaje CPU.
Nie przenosić profilu Ares7×48 na pojedynczą A10016CPU: 289 aktorów CPU się
nie zmieści. Integracja shardów/batchera oraz porównanie kompletnych metryk
na rzeczywistym GPU pozostają osobnym zadaniem. Zmiana liczby wysp nie
oznacza potwierdzenia gotowości pełnej kampanii GPU.

## Walidacja tej zmiany

Testy sprawdzają dokładne grafy i kolejność sąsiadów, wszystkie identyfikatory,
sumy kontrolne, mapowanie na uchwyty aktorów, 12×12, odrzucanie niezgodnych
liczebności i starego ER4, proweniencję oraz plan zasobów pilota.
Wyniki lokalnej sesji zapisano w katalogu workspace `artifacts/study144/`.
Nie uruchomiono zadań SLURM ani kampanii; lokalne testy nie zastępują canary HPC.
