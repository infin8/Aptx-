#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
scripts/quiet-run.sh python3 -m venv --system-site-packages .venv
scripts/quiet-run.sh .venv/bin/python -m pip --disable-pip-version-check install --progress-bar off -e '.[dev]'
