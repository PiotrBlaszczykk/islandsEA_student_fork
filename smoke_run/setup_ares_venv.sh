#!/usr/bin/env bash
set -euo pipefail

VENV_DIR="/net/people/plgrid/plgblaszczykk/venvs/islands-ray"
PROJECT_DIR="/net/people/plgrid/plgblaszczykk/islandsEA_student_fork"
PROJECT_REQUIREMENTS="${PROJECT_DIR}/islands_desync/islands_desync/geneticAlgorithm/algorithm/requirements.txt"

module load python/3.10.4-gcccore-11.3.0

if [[ ! -f "${PROJECT_REQUIREMENTS}" ]]; then
    echo "ERROR: nie znaleziono requirements projektu: ${PROJECT_REQUIREMENTS}" >&2
    echo "Najpierw sklonuj albo zaktualizuj repozytorium w ${PROJECT_DIR}." >&2
    exit 1
fi

mkdir -p "$(dirname "${VENV_DIR}")"

if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
    echo "Tworzenie venv: ${VENV_DIR}"
    python -m venv "${VENV_DIR}"
else
    echo "Uzywam istniejacego venv: ${VENV_DIR}"
fi

source "${VENV_DIR}/bin/activate"

python -m pip install --upgrade pip wheel "setuptools<81"
python -m pip install -r "${PROJECT_REQUIREMENTS}"
python -m pip install "ray==2.9.3" "scikit-learn==1.1.3" "setuptools<81"

python - <<'PY'
import importlib.metadata
import sys

print("Python:", sys.version.replace("\n", " "))
print("Executable:", sys.executable)
for package in ("ray", "jmetalpy", "numpy", "scikit-learn", "setuptools"):
    print(f"{package}: {importlib.metadata.version(package)}")
PY

echo "VENV_READY=${VENV_DIR}"

