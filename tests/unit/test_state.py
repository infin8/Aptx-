from types import SimpleNamespace

import pytest

from aptx.persistence import StateStore, VerifiedCache


def test_state_survives_restart(tmp_path):
    spec = SimpleNamespace(uri='https://example.test/a', sha256='a' * 64, expected_size=10)
    store = StateStore(tmp_path / 'state')
    store.checkpoint('a', spec, 'PAUSED', 3, '"v1"')
    store.close()
    store = StateStore(tmp_path / 'state')
    assert store.get('a')['bytes_written'] == 3
    assert store.db.execute('PRAGMA journal_mode').fetchone()[0] == 'wal'
    assert store.db.execute('PRAGMA foreign_keys').fetchone()[0] == 1
    store.close()


def test_symlinks_and_traversal_rejected(tmp_path):
    (tmp_path / 'link').symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError):
        StateStore(tmp_path / 'link')
    cache = VerifiedCache(tmp_path / 'cache')
    with pytest.raises(ValueError):
        cache.path('../escape')


def test_hardlink_not_truncated(tmp_path):
    import os

    from aptx.persistence import open_private
    original = tmp_path / 'important'
    original.write_bytes(b'preserve')
    linked = tmp_path / 'partial'
    os.link(original, linked)
    with pytest.raises(ValueError):
        open_private(linked)
    assert original.read_bytes() == b'preserve'
