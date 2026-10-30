#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
python3 - <<'PY'
from pathlib import Path
rows = [line for line in Path('GOALS.md').read_text().splitlines() if line.startswith('| G')]
passed = sum(line.rstrip().endswith('| PASS |') for line in rows)
print(f'Release gates: {passed}/12 PASS. See COMPLETION_REPORT.md and evidence/.')
raise SystemExit(0 if len(rows) == 12 and passed == 12 else 2)
PY
