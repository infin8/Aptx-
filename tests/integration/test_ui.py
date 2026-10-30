import sqlite3

import pytest
from textual.widgets import Input, Static

from aptx.tui import AptxDashboard, read_downloads, read_history


def test_default_backend_and_state_directory(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    app = AptxDashboard()
    assert app.state_dir == tmp_path / "aptx"
    assert callable(app.backend.read)


class Backend:
    def __init__(self):
        self.calls = []

    def read(self, command, packages):
        self.calls.append((command, packages))
        return {"output": "[bold]package description[/bold]"}

    def doctor(self):
        return {"healthy": True}


@pytest.mark.asyncio
async def test_search_details_theme_and_errors(tmp_path):
    backend = Backend()
    app = AptxDashboard(backend, tmp_path)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.press("enter")
        assert backend.calls == []
        app.query_one("#query", Input).value = "python3"
        await pilot.press("enter")
        await pilot.pause()
        assert backend.calls == [("search", ["python3"])]
        assert "[bold]" in str(app.query_one("#results", Static).render())
        await pilot.click("#show")
        await pilot.pause()
        assert backend.calls[-1] == ("show", ["python3"])
        before = app.theme
        await pilot.press("ctrl+t")
        assert app.theme != before
        await pilot.click("#doctor")
        await pilot.pause()
        assert "healthy" in str(app.query_one("#results", Static).render())
        await pilot.click("#downloads")
        await pilot.pause()
        assert not (tmp_path / "state.sqlite3").exists()
        await pilot.click("#history")
        await pilot.pause()
        assert "[]" in str(app.query_one("#results", Static).render())
        await pilot.click("#config")
        await pilot.pause()
        assert "state_directory" in str(app.query_one("#results", Static).render())
        await pilot.press("ctrl+r")
        await pilot.pause()
        assert "state_directory" in str(app.query_one("#results", Static).render())
        await pilot.press("ctrl+f")
        assert app.focused is app.query_one("#query", Input)


def test_downloads_reads_existing_state(tmp_path):
    db = sqlite3.connect(tmp_path / "state.sqlite3")
    db.execute("CREATE TABLE downloads(id, state, bytes_written, expected_size, updated_at)")
    db.execute("INSERT INTO downloads VALUES ('a', 'PAUSED', 10, 100, 'now')")
    db.commit()
    db.close()
    assert read_downloads(tmp_path)[0]["bytes_written"] == 10
    assert read_history(tmp_path) == []


def test_history_reads_existing_transactions(tmp_path):
    db = sqlite3.connect(tmp_path / "state.sqlite3")
    db.execute("CREATE TABLE transactions(id, command, status)")
    db.execute("INSERT INTO transactions VALUES ('a', 'install', 'complete')")
    db.commit()
    db.close()
    assert read_history(tmp_path) == [{"id": "a", "command": "install", "status": "complete"}]


def test_reject_symlink_database(tmp_path):
    target = tmp_path / "other.sqlite3"
    target.touch()
    (tmp_path / "state.sqlite3").symlink_to(target)
    with pytest.raises(ValueError, match="Symlink"):
        read_downloads(tmp_path)
    with pytest.raises(ValueError, match="Symlink"):
        read_history(tmp_path)


@pytest.mark.asyncio
async def test_backend_failure_keeps_ui_running(tmp_path):
    class BrokenBackend(Backend):
        def read(self, command, packages):
            raise RuntimeError("APT unavailable")

    app = AptxDashboard(BrokenBackend(), tmp_path)
    async with app.run_test() as pilot:
        app.query_one("#query", Input).value = "python3"
        await pilot.press("enter")
        await pilot.pause()
        assert "APT unavailable" in str(app.query_one("#results", Static).render())
        assert not app._busy
