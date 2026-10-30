#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
PYTHON=${PYTHON:-.venv/bin/python}
if [ "${1:-}" = --vm-matrix ]; then
  exec scripts/matrix.sh
fi
scripts/quiet-run.sh "$PYTHON" -m ruff check aptx tests
scripts/quiet-run.sh "$PYTHON" -m mypy aptx
scripts/quiet-run.sh "$PYTHON" -m pytest -q tests/unit tests/integration
