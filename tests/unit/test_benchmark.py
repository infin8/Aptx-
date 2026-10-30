import hashlib
import sys
from types import SimpleNamespace

import pytest

from benchmarks.run import TrustedSpec, measure, resolve, summarize, verify


def test_summary_uses_nearest_rank_p95_and_excludes_failure():
    samples = [{"ok": True, "wall_seconds": value, "user_seconds": 0.1,
                "system_seconds": 0.2, "peak_rss_kib": 40, "disk_allocated_bytes": 100}
               for value in [5, 1, 3, 2, 4]]
    samples.append({"ok": False})
    result = summarize(samples)
    assert result["median_seconds"] == 3
    assert result["p95_seconds"] == 5
    assert result["failed_runs"] == 1
    assert summarize([{"ok": False}]) == {"successful_runs": 0, "failed_runs": 1}


def test_measure_real_child_and_timeout(tmp_path):
    result = measure([sys.executable, "-c", "open('artifact', 'wb').write(b'1234')"], tmp_path)
    assert result["ok"]
    assert result["disk_logical_bytes"] == 4
    assert result["peak_rss_kib"] > 0
    result = measure([sys.executable, "-c", "import time; time.sleep(10)"], tmp_path, timeout=0.02)
    assert not result["ok"] and result["timed_out"]


def test_verify_rejects_corruption(tmp_path):
    spec = TrustedSpec("hello", "1", "https://example.test/a", 4,
                       hashlib.sha256(b"1234").hexdigest())
    path = tmp_path / "hello.deb"
    path.write_bytes(b"1234")
    assert verify(tmp_path, spec, "apt")
    path.write_bytes(b"4321")
    assert not verify(tmp_path, spec, "apt")


def test_resolve_refuses_untrusted_metadata(monkeypatch):
    candidate = SimpleNamespace(origins=[SimpleNamespace(trusted=False)])
    monkeypatch.setitem(sys.modules, "apt", SimpleNamespace(Cache=lambda: {
        "hello": SimpleNamespace(candidate=candidate)}))
    with pytest.raises(ValueError, match="trusted"):
        resolve("hello")
