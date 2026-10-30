import json

from typer.testing import CliRunner

from aptx.cli import app

runner = CliRunner()


def test_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "install" in result.stdout
    assert "doctor" in result.stdout


def test_json_config():
    result = runner.invoke(app, ["--json", "config"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["schema_version"] == 1
    assert data["ok"] is True
    assert data["error"] is None


def test_json_requires_explicit_approval(monkeypatch):
    from aptx.packages import AptBackend
    monkeypatch.setattr(AptBackend, "plan", lambda *a, **kw: {"changes": []})
    monkeypatch.setattr(AptBackend, "execute", lambda *a, **kw: (_ for _ in ()).throw(
        AssertionError("must not execute")))
    result = runner.invoke(app, ["--json", "install", "hello"])
    assert result.exit_code == 3
    assert json.loads(result.stdout)["error"]["code"] == 3


def test_dry_run_never_executes(monkeypatch):
    from aptx.packages import AptBackend
    monkeypatch.setattr(AptBackend, "plan", lambda *a, **kw: {"changes": []})
    monkeypatch.setattr(AptBackend, "execute", lambda *a, **kw: (_ for _ in ()).throw(
        AssertionError("must not execute")))
    result = runner.invoke(app, ["--json", "install", "hello", "--dry-run"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["data"] == {"changes": []}


def test_cli_hostname_download_starts_reactor(tmp_path):
    import hashlib
    import os
    import subprocess
    import sys
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    payload = b"real CLI DNS and reactor startup"

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = subprocess.run(
            [sys.executable, "-m", "aptx", "--json", "fetch",
             f"http://localhost:{server.server_port}/package",
             hashlib.sha256(payload).hexdigest(), str(len(payload))],
            env={**os.environ, "XDG_STATE_HOME": str(tmp_path / "state"),
                 "XDG_CACHE_HOME": str(tmp_path / "cache")},
            capture_output=True, text=True, timeout=15, check=False)
        assert result.returncode == 0, result.stderr + result.stdout
        assert json.loads(result.stdout)["ok"] is True
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_cli_json_usage_error():
    import subprocess
    import sys

    result = subprocess.run([sys.executable, "-m", "aptx", "--json", "unknown-command"],
                            capture_output=True, text=True, check=False, timeout=10)
    assert result.returncode == 2
    assert json.loads(result.stdout)["error"]["code"] == 2
