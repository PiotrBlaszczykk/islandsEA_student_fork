# Plan: implementacja strategii przyjmowania migrantów opartych na opóźnieniu

## Cel

Celem jest dodanie kilku eksperymentalnych strategii przyjmowania migrantów po stronie wyspy docelowej, opartych o metrykę:

```text
delay_steps = source_iteration - destination_step
```

Strategie mają służyć sprawdzeniu, czy filtrowanie migrantów według ich świeżości ewolucyjnej poprawia wynik optymalizacji, czy tylko zmniejsza opóźnienia komunikacyjne kosztem jakości rozwiązania.

## Strategie do implementacji

| Strategia | Warunek przyjęcia |
|---|---|
| `plain` | zachowuje obecne zachowanie bazowe |
| `onlyNewer` | `delay_steps > 0` |
| `newerOrAligned` | `delay_steps >= 0` |
| `rejectTooOld10` | `delay_steps >= -10` |
| `fitnessAndDelay10` | `delay_steps >= 0` albo migrant poprawia `lastBest` i `delay_steps >= -10` |
| `SASDelay10` | obecna logika `SAS`, ale z odrzuceniem migrantów `delay_steps < -10` |

Najważniejszy wariant badawczy to `onlyNewer`, czyli przyjmowanie tylko migrantów nowszych niż obecna iteracja wyspy docelowej.

```text
if delay_steps > 0:
    accept migrant
else:
    reject migrant
```

## Miejsce implementacji

Zmiany powinny wejść głównie w metodzie `add_new_individuals()` w:

```text
islands_desync/islands_desync/geneticAlgorithm/algorithm/genetic_island_algorithm.py
```

W tej metodzie dostępne są już dane potrzebne do policzenia opóźnienia:

```python
imigr_iter_list = list(emigration_at_step_num["iteration_numbers"])
delay_steps = int(imigr_iter_list[i]) - self.step_num
```

Obecnie kod tworzy `tmp_tab` z potencjalnie zaakceptowanymi migrantami, ale podmiana `new_individuals` na `tmp_tab` jest zakomentowana. Implementacja nowych strategii musi jawnie dodać do populacji tylko zaakceptowanych migrantów.

## Proponowana struktura kodu

Wydzielić pomocniczą metodę w `GeneticIslandAlgorithm`, np.:

```python
def _should_accept_migrant(
    self,
    delay_steps: int,
    migrant_fitness: float,
    destination_best_fitness: float,
    base_accept: bool,
    sas_accept: bool,
) -> tuple[bool, str]:
    ...
```

Metoda powinna zwracać:

```text
(accepted, rejection_reason)
```

Przykładowa interpretacja argumentów:

| Argument | Znaczenie |
|---|---|
| `delay_steps` | `source_iteration - destination_step` |
| `migrant_fitness` | fitness migranta w chwili wysłania |
| `destination_best_fitness` | lokalny `lastBest` wyspy docelowej |
| `base_accept` | obecny warunek: migrant poprawia `lastBest` |
| `sas_accept` | decyzja wynikająca z obecnej logiki `SAS` |

Przykładowe decyzje:

```python
strategy = self.migrant_acceptation_strategy

if strategy == "onlyNewer":
    return delay_steps > 0, "not_newer"

if strategy == "newerOrAligned":
    return delay_steps >= 0, "older_than_destination"

if strategy == "rejectTooOld10":
    return delay_steps >= -10, "older_than_threshold"

if strategy == "fitnessAndDelay10":
    accepted = delay_steps >= 0 or (
        delay_steps >= -10 and migrant_fitness < destination_best_fitness
    )
    return accepted, "not_fresh_or_improving"

if strategy == "SASDelay10":
    accepted = sas_accept and delay_steps >= -10
    return accepted, "sas_or_delay_rejected"

return base_accept, "base_rejected"
```

Uwaga: dokładny kod powinien zachować obecne zachowanie `plain` jako punkt odniesienia. Jeśli obecny baseline ma oznaczać brak filtrowania po opóźnieniu, `plain` nie powinien zmieniać wyników względem aktualnej ścieżki.

## Logowanie

Rozszerzyć logi migrantów wstecznie kompatybilnie, dodając nowe listy do payloadu zapisywanego w `W<id> Imigrants.json`.

Dodać pola:

```text
delay_steps
accepted
rejection_reasons
acceptance_strategy
```

Pola `delay_steps`, `accepted` i `rejection_reasons` powinny mieć tę samą długość co istniejące listy:

```text
iteration_numbers
timestamps
src_islands
fitnesses
```

Przykładowe powody odrzucenia:

| Powód | Znaczenie |
|---|---|
| `accepted` | migrant przyjęty |
| `not_newer` | odrzucony przez `onlyNewer` |
| `older_than_destination` | odrzucony przez `newerOrAligned` |
| `older_than_threshold` | odrzucony przez próg `rejectTooOld10` |
| `not_fresh_or_improving` | odrzucony przez `fitnessAndDelay10` |
| `sas_or_delay_rejected` | odrzucony przez `SASDelay10` |
| `base_rejected` | odrzucony przez bazowy warunek poprawy fitness |

## Aktualizacja analizy

Zaktualizować `islands_desync/analyze_migration_delays.py`, żeby obsługiwał nowe pola, ale nie wymagał ich dla starych logów.

Zasady:

- jeśli `accepted` istnieje, raportować realne `accepted_count` i `rejected_count`;
- jeśli `accepted` nie istnieje, zachować obecne pola inferowane;
- dodać histogram `rejection_reasons_histogram` do `summary.json`;
- nie zmieniać istniejących nazw wykresów ani katalogu `analysis_migration`;
- nie usuwać obecnych pól, żeby stare raporty nadal działały.

## Minimalny test plan

Import:

```bash
cd islands_desync
PYTHONPATH="$PWD" ../.venv/bin/python -c "from islands_desync.geneticAlgorithm.algorithm.genetic_island_algorithm import GeneticIslandAlgorithm"
```

Runy lokalne dla nowych strategii:

```bash
cd islands_desync
dda=$(date +%y%m%d)
tta=$(date +%H%M%S)
PYTHONPATH="$PWD" python -u islands_desync/start.py 7 /tmp/islands-ray 5 5 "$dda" "$tta" ring random onlyNewer
```

Powtórzyć dla:

```text
newerOrAligned
rejectTooOld10
fitnessAndDelay10
SASDelay10
```

Minimum porównawcze:

```text
ring random plain
ring random onlyNewer
complete best plain
complete best onlyNewer
```

Po każdym runie:

```bash
python analyze_migration_delays.py "<run_dir>"
```

Sprawdzić w `summary.json`:

- `received_count > 0`
- `accepted_count <= received_count`
- `rejected_count >= 0`
- `rejection_reasons_histogram` istnieje dla nowych logów
- `delay_steps` zachowuje znak
- final best fitness i final average fitness są nadal raportowane

## Kryteria akceptacji

Implementacja jest gotowa, jeśli:

- wszystkie strategie można wybrać 9. argumentem `start.py`;
- `plain` działa jako baseline;
- `onlyNewer` faktycznie przyjmuje tylko migrantów z `delay_steps > 0`;
- nowe logi pokazują, którzy migranci zostali przyjęci i dlaczego inni zostali odrzuceni;
- `analyze_migration_delays.py` działa zarówno na starych, jak i nowych logach;
- lokalny run na 7 wyspach dochodzi do końca dla co najmniej `plain`, `onlyNewer` i `rejectTooOld10`.

## Założenia

- Implementujemy strategie przyjmowania migrantów, nie strategie wyboru migrantów po stronie źródłowej.
- Nie zmieniamy topologii, harmonogramu migracji ani formatu nazw katalogów wynikowych.
- Nowe strategie są eksperymentalne i muszą być porównywane z `plain` przy tych samych parametrach eksperymentu.
- Każda zmiana semantyki przyjmowania migrantów wpływa na porównywalność wyników, więc raport musi zawsze zawierać także metryki jakości optymalizacji, nie tylko opóźnienia.
