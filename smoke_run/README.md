# Ares smoke test

Minimalny test sprawdza trzy rzeczy:

1. job SLURM uruchamia się na węźle obliczeniowym,
2. używany jest venv `/net/people/plgrid/plgblaszczykk/venvs/islands-ray`,
3. Ray potrafi wystartować i wykonać zdalną funkcję.

## Położenie

Katalog `smoke_run` znajduje się wewnątrz repozytorium `islandsEA_student_fork`, więc jest
przenoszony na Aresa przez zwykły workflow `commit -> push -> git pull`.

## 1. Przygotowanie venv na Aresie

Po umieszczeniu katalogu w `~/islandsEA_student_fork/smoke_run`:

```bash
cd ~/islandsEA_student_fork
git pull --ff-only
cd smoke_run
bash setup_ares_venv.sh
```

Skrypt tworzy lub aktualizuje:

```text
/net/people/plgrid/plgblaszczykk/venvs/islands-ray
```

Instaluje wymagania projektu oraz `ray==2.9.3`, `scikit-learn==1.1.3` i `setuptools<81`.

## 2. Wysłanie smoke joba

```bash
cd ~/islandsEA_student_fork/smoke_run
JOB_ID=$(sbatch --parsable run_smoke.sh)
echo "JOB_ID=${JOB_ID}"
squeue -j "${JOB_ID}"
```

Jeżeli konto nie ma domyślnego grantu SLURM, dodaj właściwy `#SBATCH --account=...` do
`run_smoke.sh` przed wysłaniem zadania.

Po zakończeniu:

```bash
cat "slurm-${JOB_ID}.out"
```

Poprawny wynik kończy się linią:

```text
SMOKE_TEST_OK
```

Job nie uruchamia właściwego benchmarku i nie korzysta z węzła logowania do obliczeń.

## Końce linii

Reguła w `.gitattributes`:

```text
*.sh text eol=lf
```

wymusza linuksowe końce linii LF dla skryptów Bash. `.gitignore` ignoruje natomiast pliki
`slurm-*.out`, cache Pythona i lokalne venvy.
