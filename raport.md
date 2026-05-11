# Wykresy opóźnień na wyspach w zależności od strategii 
Poniżej przedstawiam przykładowe wykresy generowane na podstawie lokalnego uruchumienia algorytmu na 7 wyspach. Na razie bez żadnych zmian heurystyki:

## Metryka użyta na wykresach
Wykresy pokazują opóźnienie migracji liczone w krokach algorytmu:

```text
delay_steps = source_iteration - destination_step
```

gdzie:
- `source_iteration` to numer iteracji na wyspie źródłowej w chwili wysłania migranta,
- `destination_step` to numer kroku na wyspie docelowej w chwili jego odebrania.

Interpretacja:
- `delay_steps < 0` oznacza migranta opóźnionego,
- `delay_steps = 0` oznacza migranta zsynchronizowanego,
- `delay_steps > 0` oznacza migranta przyspieszonego.

Każdy panel na wykresie odpowiada jednej wyspie docelowej i pokazuje wartości `delay_steps` kolejnych odebranych migrantów w funkcji kroku wyspy docelowej.

## Potencjalne strategie przyjmowania migrantów oparte na opóźnieniach

Najprostsza strategia przyjmowania migrantów to przyjmowanie tylko migrantów nowszych niż obecna iteracja wyspy docelowej.

```text
if delay_steps > 0:
    accept migrant
else:
    reject migrant
```

Taki wariant nazwiemy `onlyNewer`. Odrzuca on migrantów opóźnionych oraz zsynchronizowanych, a zostawia tylko tych, których źródło było ewolucyjnie dalej niż wyspa docelowa w chwili wysłania. To jest bardzo agresywna polityka, bo w tych danych udział migrantów przyspieszonych wynosi tylko około `20-30%`.

Pomysły na alternatywne strategie:

- `plain`: punkt odniesienia bez filtrowania po opóźnieniu.
- `onlyNewer`: przyjmuj tylko migrantów z `delay_steps > 0`.
- `newerOrAligned`: przyjmuj migrantów z `delay_steps >= 0`
- `rejectTooOldK`: odrzucaj tylko migrantów silnie opóźnionych, np. `delay_steps < -10`.
- `delayWindow`: przyjmuj migrantów z okna `-K <= delay_steps <= A`, np. `-10 <= delay_steps <= 20`.
- `fitnessAndDelay`: przyjmuj migranta, jeśli jest nowszy od wyspy docelowej albo jeśli poprawia lokalny najlepszy fitness.
- inne warianty z ideą `SAS` - czekam na odpowiedź P. Białaszek czym docelowo miało być SAS

## Testy nowych strategii
Zaimplementowałem przykładowe strategie, dodatkowo naprawiłem strategię `best` która do tej pory nie działała poprawnie. Żeby przeanalizować, że strategie faktycznie
działają i filtrują migrantów, narysowałem wykresy opóźnienia migrantów dla każdej wyspy.

### Opóźnienia przy strategii `plain`
Przyjmujemy wszystkich migrantów.

<img src="raport_imgs/delays_plain.png" alt="plain" width="600"/>

### Opóźnienia przy strategii `rejectTooOldK`
Przyjmujemy tylko migrantów, którzy nie są silnie opóźnieni, tutaj `10` kroków czyli `delay_steps >= -10`.

<img src="raport_imgs/delays_too_old_k.png" alt="rejectTooOldK" width="600"/>

# Eksperymenty `Sphere 200`, topologia `ring`:
Poniżej wyniki eksperymentów dla 150 wysp dla różnych strategii. Wykresy przedstawiają ewolucję najlepszego fitnessu w funkcji liczby kroków algorytmu.

<table>
    <tr>
        <th> <center> Strategia `plain` </center> </th>
        <th> <center> Strategia `newer` </center> </th>
    </tr>
    <tr>
        <td><img src="raport_imgs/fitness_plain.png" alt="plain" width="400"/></td>
        <td><img src="raport_imgs/fitness_newer.png" alt="newer" width="400"/></td>
    </tr>
    <tr>
        <th> <center> Strategia `window:10` </center> </th>
        <th> <center> Strategia `rejectTooOld:10` </center> </th>
    </tr>
    <tr>
        <td><img src="raport_imgs/fitness_window.png" alt="window:10" width="400"/></td>
        <td><img src="raport_imgs/fitness_too_old.png" alt="rejectTooOld:10" width="400"/></td>
    </tr>
    <tr>
        <th> <center> Strategia `better` </center> </th>
        <th> </th>
    </tr>
    <tr>
        <td><img src="raport_imgs/fitness_better.png" alt="better" width="400"/></td>
        <td></td>
    </tr>
</table>

## Podsumowanie

| Strategy       | Average Result | Best Result | Avg Delay | Min Delay | Max Delay | Median Delay |
|----------------|----------------|-------------|-----------|-----------|-----------|--------------|
| plain          | 3.78 | 0.60 | -0.21 | -555 | 541 | -2 |
| newer          | 38.50 | 19.67 | 48.45 | 0 | 583 | 25 |
| window:10      | 32.74 | 15.23 | -1.50 | -10 | 10 | -2 |
| rejectTooOld:10 | 28.65 | 10.52 | 13.69 | -10 | 584 | -2 |
| better         | 4.16 |  0.70 | 6.22 | -559 | 548 | -1 |

# Wnioski:
Przy topologii ring i 150 wyspach, ograniczanie przepływu migrantów znacząco zmniejsza różnorodność populacji, co prowadzi do gorszych wyników. Jako następne przetestujemy inne topologie.
