"""Private, versioned SQLite state and content-addressed verified cache."""
import hashlib
import os
import sqlite3
import stat
from pathlib import Path


def private_directory(path: Path) -> Path:
    path = Path(path).absolute()
    for component in (path, *path.parents):
        if component.is_symlink():
            raise ValueError(f"Symlink directory refused: {component}")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.stat().st_uid != os.getuid():
        raise ValueError("State/cache directory must belong to current user")
    path.chmod(0o700)
    return path


def open_private(path: Path, append: bool = False):
    flags = os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW
    flags |= os.O_APPEND if append else 0
    fd = os.open(path, flags, 0o600)
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid():
        os.close(fd)
        raise ValueError("Unsafe download file")
    if not append:
        os.ftruncate(fd, 0)
    return os.fdopen(fd, 'ab' if append else 'wb')


class StateStore:
    def __init__(self, directory: Path):
        self.directory = private_directory(directory)
        path = self.directory / 'state.sqlite3'
        if path.is_symlink():
            raise ValueError('Symlink database refused')
        with open_private(path, append=True):
            pass
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.execute('PRAGMA busy_timeout=5000')
        version = self.db.execute('PRAGMA user_version').fetchone()[0]
        if version > 2:
            raise ValueError('State database is newer than this application')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS downloads(
          id TEXT PRIMARY KEY, uri TEXT NOT NULL, expected_sha256 TEXT NOT NULL,
          expected_size INTEGER NOT NULL, etag TEXT, state TEXT NOT NULL,
          bytes_written INTEGER NOT NULL DEFAULT 0, updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS cache_blobs(
          digest TEXT PRIMARY KEY, size INTEGER NOT NULL, path TEXT NOT NULL,
          verified_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS transactions(
          id TEXT PRIMARY KEY, command TEXT, plan_json TEXT, status TEXT,
          exit_code INTEGER, started_at TEXT DEFAULT CURRENT_TIMESTAMP, finished_at TEXT);
        PRAGMA user_version=2;
        ''')

        columns = {row[1] for row in self.db.execute('PRAGMA table_info(downloads)')}
        if 'expected_sha512' not in columns:
            self.db.execute('ALTER TABLE downloads ADD COLUMN expected_sha512 TEXT')
            self.db.commit()

    def get(self, key):
        return self.db.execute('SELECT * FROM downloads WHERE id=?', (key,)).fetchone()

    def checkpoint(self, key, spec, state, count=0, etag=None):
        with self.db:
            self.db.execute('''INSERT INTO downloads
              (id,uri,expected_sha256,expected_size,etag,state,bytes_written,expected_sha512)
              VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
              state=excluded.state, bytes_written=excluded.bytes_written,
              etag=excluded.etag, updated_at=CURRENT_TIMESTAMP''',
              (key, spec.uri, spec.sha256, spec.expected_size, etag, state, count, getattr(spec, "sha512", None)))

    def close(self):
        self.db.close()


class VerifiedCache:
    def __init__(self, directory: Path):
        self.directory = private_directory(directory)

    def path(self, digest):
        if len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
            raise ValueError('Invalid SHA256')
        return self.directory / digest

    def verify(self, path, spec):
        if path.is_symlink():
            raise ValueError('Symlink blob refused')
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        except FileNotFoundError:
            return False
        sha256, sha512, size = hashlib.sha256(), hashlib.sha512(), 0
        with os.fdopen(fd, 'rb') as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ValueError('Unsafe cache blob')
            while block := stream.read(1024 * 1024):
                size += len(block)
                sha256.update(block)
                sha512.update(block)
        return (size == spec.expected_size and sha256.hexdigest() == spec.sha256
                and (spec.sha512 is None or sha512.hexdigest() == spec.sha512))
