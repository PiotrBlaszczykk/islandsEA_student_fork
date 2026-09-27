# Kampanie Ares / 40 benchmarków / 3 powtórzenia

## BA / best, random, maxDistance

Trzy kampanie `ba` używają dokładnej instancji Barabásiego-Alberta z
załącznika `BA grapf - 144 nodes.txt`: 144 węzły, `m0=30`, `m=30`,
3855 krawędzi nieskierowanych. Oryginalne identyfikatory i kolejność
sąsiadów są zachowane. Plan oraz walidator wymagają parametrów,
pochodzenia pliku i hasha uporządkowanej adjacencji
`6f261e5960a86e2e13112f77748dff316207f5802022f99f98edabb1fadc1e00`.
Graf nie jest generowany ponownie między runami.

Każda kampania obejmuje 40 benchmarków przy D=200 i trzy niezależne
powtórzenia: 120 runów z 144 wyspami, 8000 ewaluacji na wyspę,
populacją 16, offspring 4, pięcioma migrantami co pięć ewaluacji,
akceptacją `plain` i pełnymi metrykami. Profil Ares to 7×48 CPU na run;
jednocześnie pracują najwyżej trzy elementy array. Zmienia się tylko
strategia wyboru migrantów.

Po commicie/pushu na `summer_ares_blaszczyk` i `git pull --ff-only` na Aresie
uruchamiaj **po jednej kampanii na raz**:

| Strategia | Launcher | Katalog na scratch | Pobieranie na Windowsie |
|---|---|---|---|
| best | `bash main_runs/launch_ba_best.sh` | `$SCRATCH/ba_best` | `.\main_runs\download_ba_best.ps1` |
| random | `bash main_runs/launch_ba_random.sh` | `$SCRATCH/ba_random` | `.\main_runs\download_ba_random.ps1` |
| maxDistance | `bash main_runs/launch_ba_maxdistance.sh` | `$SCRATCH/ba_maxdistance` | `.\main_runs\download_ba_maxdistance.ps1` |

Launcher sprawdza wszystkie 40 kombinacji dry-runem przed wysłaniem
120-elementowego array i finalizera `afterany`. Po zakończeniu sprawdź
121 wpisów `COMPLETED|0:0`, znacznik `BA_<STRATEGY>_VALID_RUNS=120`
oraz `BA_<STRATEGY>_FINALIZATION_OK`. W znaczniku `maxDistance` ma postać
`MAXDISTANCE`, a w ścieżkach `maxdistance`. Finalizer tworzy jedno archiwum
`ba_<strategia>.tar.gz` z SHA-256 tylko przy 120 zweryfikowanych runach.
Downloadery domyślnie pobierają tar bez rozpakowania i sprawdzają SHA-256;
`-Extract` wymaga dodatkowego miejsca. Po sprawdzeniu lokalnej kopii
zwolnij katalog zakończonej kampanii na scratch przed następną.
W razie pojedynczej porażki po diagnozie użyj odpowiednio
`retry_ba_best_task.sh`, `retry_ba_random_task.sh` lub
`retry_ba_maxdistance_task.sh` z argumentem `<TASK_ID>`.

## Complete / best, random, maxDistance

Trzy kampanie `complete` obejmują po 120 niezależnych runów: 144 wyspy,
40 benchmarków przy D=200 i trzy powtórzenia. Każda zachowuje 8000 ewaluacji
na wyspę, populację 16, offspring 4, pięciu migrantów co pięć ewaluacji,
akceptację `plain`, pełne metryki i profil Ares 7×48 CPU. Zmienia się
wyłącznie strategia wyboru migrantów: `best`, `random` albo `maxDistance`.
Graf pełny łączy każdy węzeł ze wszystkimi pozostałymi: 144 węzły,
20 592 skierowane wpisy sąsiedztwa, bez pętli. Walidator wymaga dokładnego
uporządkowania list sąsiadów, hasha
`ce2d15a0567515f9b81654814679a265e83e2395f4e90fb609cd7301ee196062`
oraz zgodności strategii w planie, metadanych i `topology.json`.

Po commicie/pushu na `summer_ares_blaszczyk` i `git pull --ff-only` na Aresie
uruchamiaj **jedną kampanię na raz**, w tej kolejności:

| Strategia | Launcher | Katalog na scratch | Pobieranie na Windowsie |
|---|---|---|---|
| best | `bash main_runs/launch_complete_best.sh` | `$SCRATCH/complete_best` | `.\main_runs\download_complete_best.ps1` |
| random | `bash main_runs/launch_complete_random.sh` | `$SCRATCH/complete_random` | `.\main_runs\download_complete_random.ps1` |
| maxDistance | `bash main_runs/launch_complete_maxdistance.sh` | `$SCRATCH/complete_maxdistance` | `.\main_runs\download_complete_maxdistance.ps1` |

Każdy launcher wykonuje 40 dry-runów preflight i wysyła 120-elementowy array
z limitem trzech jednoczesnych tasków oraz finalizer `afterany`. Nazwy
archiwów to odpowiednio `complete_best.tar.gz`, `complete_random.tar.gz`
i `complete_maxdistance.tar.gz`, każde z plikiem `.sha256`. Po zakończeniu
sprawdź 121 rekordów `COMPLETED|0:0` oraz znaczniki
`COMPLETE_<STRATEGY>_VALID_RUNS=120` i
`COMPLETE_<STRATEGY>_FINALIZATION_OK` w logu finalizera. W znacznikach
`maxDistance` ma postać `MAXDISTANCE`; ścieżki używają małych liter.

Helpery pobierają archiwum i sprawdzają SHA-256 bez rozpakowania. Po
potwierdzeniu lokalnej kopii oraz 120 poprawnych runów zwolnij katalog
zakończonej kampanii na scratch przed uruchomieniem następnej, aby nie
przekroczyć kwoty plików. Opcja `-Extract` wymaga dodatkowego miejsca.
W razie pojedynczego nieudanego tasku po diagnozie użyj odpowiednio
`retry_complete_best_task.sh`, `retry_complete_random_task.sh` lub
`retry_complete_maxdistance_task.sh` z argumentem `<TASK_ID>`.

## WS3 / maxDistance

`main_runs/launch_ws3_maxdistance.sh` uruchamia 120 niezależnych runów na tej
samej, zamrożonej instancji WS3 co kampanie `best` i `random`: 40 benchmarków
przy D=200, trzy powtórzenia, 144 wyspy, pełne metryki i profil 7×48 CPU.
Wybór migrantów to dokładnie `maxDistance` (wielkość liter ma znaczenie),
akceptacja pozostaje `plain`. Maksymalnie trzy elementy array pracują
jednocześnie. Plan, metadane runów i finalizer walidują strategię oraz
tożsamość grafu WS3.

Po pobraniu archiwum WS3/random i potwierdzeniu SHA-256 oraz
`WS3_RANDOM_VALID_RUNS=120` można zwolnić `$SCRATCH/ws3_random`, aby odzyskać
kwotę plików. Po commicie/pushu i `git pull --ff-only` na Aresie uruchom:

```bash
bash main_runs/launch_ws3_maxdistance.sh
```

Wyniki trafiają wyłącznie do `$SCRATCH/ws3_maxdistance`. Po zakończeniu
sprawdź 120 elementów array i finalizer jako `COMPLETED 0:0` oraz znaczniki
`WS3_MAXDISTANCE_VALID_RUNS=120` i `WS3_MAXDISTANCE_FINALIZATION_OK` w
`$SCRATCH/ws3_maxdistance/logs/ws3-maxdistance-finalize-<ID>.out`. Dopiero
wtedy finalizer tworzy `ws3_maxdistance.tar.gz` i `.sha256`. Pojedynczy
nieudany task można po diagnozie ponowić jawnie:

```bash
bash main_runs/retry_ws3_maxdistance_task.sh <TASK_ID>
```

Na Windowsie pobierz jedno archiwum i sprawdź jego SHA-256 bez rozpakowania:

```powershell
.\main_runs\download_ws3_maxdistance.ps1
```

Opcja `-Extract` dodatkowo weryfikuje 120 wewnętrznych bundle i zajmuje
więcej miejsca na dysku.

## WS3 / random

`main_runs/launch_ws3_random.sh` uruchamia tę samą zamrożoną instancję WS3 i
ten sam profil 144 wysp, D=200, 40 benchmarków × 3 powtórzenia co kampania
WS3/best. Jedyną zmianą naukową jest selekcja migrantów `random`; akceptacja
pozostaje `plain`. Plan, metadane każdego runu i finalizer wymagają zgodnej
strategii oraz dokładnego grafu WS3. Maksymalnie trzy z 120 elementów array
pracują jednocześnie.

Po pobraniu i sprawdzeniu SHA-256 archiwum WS3/best oraz potwierdzeniu
`WS3_BEST_VALID_RUNS=120` można zwolnić jego katalog na Aresie, aby odzyskać
kwotę plików. Następnie, po commicie/pushu i `git pull --ff-only` na Aresie:

```bash
bash main_runs/launch_ws3_random.sh
```

Wyniki są odseparowane w `$SCRATCH/ws3_random`. Po zakończeniu wymagane są
120 elementów array i finalizer w stanie `COMPLETED 0:0`, a w
`$SCRATCH/ws3_random/logs/ws3-random-finalize-<ID>.out` znaczniki
`WS3_RANDOM_VALID_RUNS=120` i `WS3_RANDOM_FINALIZATION_OK`. Finalizer tworzy
`ws3_random.tar.gz` oraz `.sha256` dopiero po pełnej walidacji. Pojedynczy
nieudany task można jawnie ponowić przez
`bash main_runs/retry_ws3_random_task.sh <TASK_ID>`.

Na Windowsie pobierz jedno archiwum i zweryfikuj sumę bez rozpakowywania:

```powershell
.\main_runs\download_ws3_random.ps1
```

Opcja `-Extract` sprawdza także 120 wewnętrznych bundle, lecz wymaga
dodatkowego miejsca na dysku.

## WS3 / best

`main_runs/launch_ws3_best.sh` uruchamia 120 niezależnych runów: zamrożony
graf WS3 z załącznika (`ws3`, 144 wyspy), selekcja migrantów `best`, akceptacja
`plain`, 30 benchmarków ciągłych i 10 binarnych przy D=200, po trzy
powtórzenia. Pozostałe parametry są takie same jak dla Torusa: 8000 ewaluacji
na wyspę, populacja 16, offspring 4, pięciu migrantów co pięć ewaluacji,
baza seedów 20260912, pełne metryki i profil Ares 7×48 CPU. Jednocześnie
pracują najwyżej trzy elementy tablicy.

Plan i walidator wymagają dokładnej instancji WS3: 144 węzłów, parametrów
`dim=2`, `lat=12`, `nei=3`, `probab=0.003181`, `scenario=2`, pochodzenia
załącznika i hasha pełnej, uporządkowanej listy sąsiadów. Nie losujemy grafu
ponownie. Każdy run zachowuje `topology.json` i `topology.png`; finalizer
tworzy `$SCRATCH/ws3_best/ws3_best.tar.gz` i SHA-256 tylko przy 120
zweryfikowanych runach. Osobne archiwa runów pozostają w zbiorczym tarze.

Po commicie i pushu brancha `summer_ares_blaszczyk` wykonaj na Aresie
`git pull --ff-only`. Sprawdź `hpc-fs`; starszą kampanię
`torus_maxdistance` usuń ze SCRATCH dopiero po pobraniu i lokalnym
potwierdzeniu SHA-256, podsumowania `valid_runs=120` i obecności 120 bundle.
Potem uruchom:

```bash
bash main_runs/launch_ws3_best.sh
```

Po zakończeniu wymagane są 120 elementów tablicy i finalizer w stanie
`COMPLETED 0:0` oraz `WS3_BEST_VALID_RUNS=120` i
`WS3_BEST_FINALIZATION_OK` w
`$SCRATCH/ws3_best/logs/ws3-best-finalize-<ID>.out`.
W razie pojedynczej porażki, po diagnozie uruchom jawny retry:

```bash
bash main_runs/retry_ws3_best_task.sh <TASK_ID>
```

Na Windowsie pobierz jedno archiwum bez rozpakowania i sprawdź jego SHA-256:

```powershell
.\main_runs\download_ws3_best.ps1
```

Opcja `-Extract` dodatkowo sprawdza SHA-256 120 wewnętrznych archiwów, ale
zużywa około drugie tyle miejsca. Do lokalnej weryfikacji podsumowania można
odczytać `campaign_summary.json` bez rozpakowywania całego tara.

## Torus / best, random i maxDistance

Trzecia kampania zmienia wyłącznie strategię wyboru migrantów na
`maxDistance`; strategia przyjmowania pozostaje `plain`. Zachowuje ten sam
torus 12×12, 144 wyspy, D=200, 40 benchmarków, trzy niezależne powtórzenia,
profil 7×48 CPU i najwyżej trzy równoległe taski. Dane trafiają wyłącznie do
`$SCRATCH/torus_maxdistance`, a finalizer tworzy
`torus_maxdistance.tar.gz` i jego SHA-256 po pozytywnej walidacji 120 runów.
Po commicie i pushu brancha `summer_ares_blaszczyk` wykonaj na Aresie
`git pull --ff-only`. Przed uruchomieniem sprawdź `hpc-fs`; zakończoną kampanię
`torus_random` usuń ze SCRATCH dopiero po pobraniu i lokalnym potwierdzeniu
SHA-256 oraz `valid_runs=120`. Pozwala to odzyskać quota plików. Następnie:

```bash
bash main_runs/launch_torus_maxdistance.sh
```

Po zakończeniu wymagana jest para `COMPLETED 0:0`,
`TORUS_MAXDISTANCE_VALID_RUNS=120` i `TORUS_MAXDISTANCE_FINALIZATION_OK` w
`$SCRATCH/torus_maxdistance/logs/torus-maxdistance-finalize-<ID>.out`.
W razie pojedynczego nieudanego tasku dostępny jest jawny retry:

```bash
bash main_runs/retry_torus_maxdistance_task.sh <TASK_ID>
```

Na Windowsie pobierz jedno archiwum i sprawdź jego SHA-256 bez rozpakowania:

```powershell
.\main_runs\download_torus_maxdistance.ps1
```

`-Extract` dodatkowo sprawdza SHA-256 wszystkich 120 wewnętrznych bundle,
ale wymaga drugie tyle miejsca na dysku. Archiwa pojedynczych runów pozostają
oddzielne w zbiorczym tarze. Do czasu pobrania i weryfikacji nie kasuj
surowych danych ze SCRATCH.

Druga, niezależna kampania z wyborem migrantów `random` ma launcher
`main_runs/launch_torus_random.sh` i zapisuje wszystko pod
`$SCRATCH/torus_random`. Ma tę samą macierz 40×3 i profil Ares; jedyną zmianą
naukową jest `--strategy random` zamiast `best`. Wykorzystuje wspólny skrypt
batch i finalizer, które odczytują strategię z jawnie eksportowanej zmiennej.
Plan i metadane muszą się z nią zgadzać. Po commicie, pushu i pullu brancha
`summer_ares_blaszczyk` uruchom na Aresie:

```bash
bash main_runs/launch_torus_random.sh
```

Skrypt wypisze ID tablicy i finalizera. Po ich zakończeniu wymagane są
`COMPLETED 0:0`, `TORUS_RANDOM_VALID_RUNS=120` i
`TORUS_RANDOM_FINALIZATION_OK` w
`$SCRATCH/torus_random/logs/torus-random-finalize-<ID>.out`.
Jeżeli padnie pojedynczy task, po diagnozie można go ponowić przez
`bash main_runs/retry_torus_random_task.sh <TASK_ID>`.

Na Windowsie pobierz jedno archiwum:

```powershell
.\main_runs\download_torus_random.ps1
```

Domyślnie helper pobiera `torus_random.tar.gz` i sprawdza jego SHA-256 bez
rozpakowywania. Opcja `-Extract` dodatkowo tworzy katalog z 120 nadal
skompresowanymi archiwami i sprawdza ich osobne SHA-256; wymaga przez to około
drugie tyle miejsca. Przenośne bundle pozostają oddzielne dla każdego runu.

Przed wysłaniem drugiej kampanii sprawdź na Aresie `hpc-fs`, które pokazuje
również liczbę użytych plików. `ARES_INFO.md` podaje limit miliona inode'ów; pozostawione
surowe i wyeksportowane katalogi `torus_best` zajmują znaczną część tej puli.
Launcher sprawdza wolne bajty, ale `df` nie odzwierciedla wiarygodnie osobistej
kwoty inode'ów na tym storage.

Poniżej zachowano instrukcję pierwszej kampanii `best`.

`launch_torus_best.sh` wysyła na Aresie dokładnie 120 niezależnych runów:

- 30 problemów ciągłych `r01`–`r30` i 10 binarnych `b01`–`b10`;
- D=200, 144 wyspy, torus 12×12;
- selekcja `best`, akceptacja `plain`, 5 migrantów co 5 ewaluacji;
- populacja 16, offspring 4, po 8000 ewaluacji na wyspę;
- trzy powtórzenia z bazą seedów 20260912.

Array ma 120 elementów i domyślnie dopuszcza najwyżej trzy jednocześnie. Każdy
element używa sprawdzonego profilu 7×48 CPU, waliduje dane naukowe 144 wysp,
tworzy własny przenośny bundle i weryfikuje go jeszcze wewnątrz swojej
alokacji. Nie ma automatycznych retry.

Finalizer działa przez `afterany`, ale tworzy finalne archiwum tylko wtedy, gdy
wszystkie 120 tasków zakończyły się kodem 0, walidacja naukowa i każdy bundle
przeszły weryfikację, a metadane dokładnie odpowiadają planowi. Wynik znajduje
się w jednym drzewie:

```text
$SCRATCH/torus_best/
├── campaign_plan.json
├── submission.json
├── campaign_summary.json
├── sacct.txt
├── logs/                          # pełne logi na scratchu; snapshot w tar.gz
├── tasks/
├── runs/                         # pojedyncze bundle i ich SHA-256
├── storage/                      # zachowane raw/audit; nie kasować przed pobraniem
├── torus_best.tar.gz             # 120 bundle, plan, wyniki kontroli, logi
└── torus_best.tar.gz.sha256
```

Archiwum zbiorcze zawiera 120 pełnych przenośnych bundle, plan, podsumowanie,
rekordy zadań, logi i `sacct.txt`. Surowe katalogi w `storage/` pozostają na
scratchu jako niezależna kopia do czasu pobrania i weryfikacji archiwum.

Po commicie i pushu brancha `summer_ares_blaszczyk`, wykonaj
`git pull --ff-only` na Aresie. Następnie, z czystego checkoutu:

```bash
bash main_runs/launch_torus_best.sh
```

Launcher wypisuje `TORUS_BEST_ARRAY_JOB_ID` i `TORUS_BEST_FINALIZER_JOB_ID`.
Podczas pracy oraz po niej:

```bash
squeue -j ARRAY_ID,FINALIZER_ID -o "%.18i %.24j %.10T %.10M %.10l %R"
sacct -X -j ARRAY_ID,FINALIZER_ID --format=JobID,JobName,State,ExitCode,Elapsed,AllocCPUS,CPUTimeRAW
grep -E 'TORUS_BEST_(VALID_RUNS|ARCHIVE|SHA256)|TORUS_BEST_FINALIZATION_OK' \
  "$SCRATCH/torus_best/logs/torus-best-finalize-FINALIZER_ID.out"
```

Jeśli finalizer zakończy się błędem, `campaign_summary.json` zawiera listę
nieudanych lub brakujących tasków. Pozostałe dane zostają na scratchu;
skrypt nie uruchamia ich ponownie automatycznie.

Pojedynczy task, który ma w `task.json` status `failed`, można wznowić jawnie
bez ponawiania pozostałych 119 runów. Helper zachowuje identyfikator pierwotnej
kampanii, wysyła wskazany task jako nową jednoelementową tablicę i po nim nowy
finalizer. Przykład dla tasku 104:

```bash
bash main_runs/retry_torus_best_task.sh 104
```

Szczytowa równoległość to 3 runy, czyli 21 węzłów i 1008 przydzielonych CPU.
Można ją zmniejszyć, np. `TORUS_BEST_MAX_PARALLEL=2`, ale nie zwiększyć ponad 3.
Godzinny walltime na run daje sufit 40320 CPUh dla 120 runów; jest to
bezpiecznik, a nie prognoza ani koszt naliczany za cały zarezerwowany limit.
Pilot F1 trwał około 1:47, ale inne benchmarki mogą być znacznie wolniejsze.
Dodatkowy czas zabierają walidacja danych i eksport.

Po markerze `TORUS_BEST_FINALIZATION_OK` pobiera się tylko archiwum zbiorcze i
checksumę. Helper wykonuje jedno `scp`, więc SSH pyta o hasło jeden raz, a
potem sprawdza SHA-256:

```powershell
.\main_runs\download_torus_best.ps1 -Extract
```

Jeżeli `$SCRATCH` na Aresie ma inną ścieżkę niż obecnie potwierdzona, należy
podać `-RemoteCampaignDir '/właściwe/SCRATCH/torus_best'`.
