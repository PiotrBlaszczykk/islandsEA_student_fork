# Kampanie Torus / best i random / 40 benchmarków / 3 powtórzenia

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
