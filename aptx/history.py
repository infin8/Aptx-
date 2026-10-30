"""Per-user native transaction audit trail, separate from authoritative APT state."""
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from .persistence import StateStore


def record(directory: Path, command: str, plan: dict, status: str, exit_code: int) -> None:
    store = StateStore(directory)
    try:
        with store.db:
            store.db.execute('''CREATE TABLE IF NOT EXISTS transactions(
                id TEXT PRIMARY KEY, command TEXT, plan_json TEXT, status TEXT,
                exit_code INTEGER, started_at TEXT, finished_at TEXT)''')
            now = datetime.now(UTC).isoformat()
            store.db.execute('INSERT INTO transactions VALUES(?,?,?,?,?,?,?)',
                             (uuid.uuid4().hex, command, json.dumps(plan), status, exit_code, now, now))
    finally:
        store.close()
