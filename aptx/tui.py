"""Unprivileged package browser and local download status dashboard."""
from __future__ import annotations

import asyncio
import json
import os
import sqlite3
from pathlib import Path
from typing import Any, ClassVar

from textual.app import App, ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, Footer, Header, Input, Static


def read_downloads(directory: Path) -> list[dict[str, Any]]:
    """Read existing state without creating a database or changing its schema."""
    path = directory / "state.sqlite3"
    if not path.exists():
        return []
    if path.is_symlink():
        raise ValueError("Symlink database refused")
    db = sqlite3.connect(path.absolute().as_uri() + "?mode=ro", uri=True)
    try:
        db.row_factory = sqlite3.Row
        return [dict(row) for row in db.execute(
            "SELECT id, state, bytes_written, expected_size, updated_at "
            "FROM downloads ORDER BY updated_at DESC LIMIT 200"
        )]
    finally:
        db.close()


def read_history(directory: Path) -> list[dict[str, Any]]:
    path = directory / "state.sqlite3"
    if not path.exists():
        return []
    if path.is_symlink():
        raise ValueError("Symlink database refused")
    db = sqlite3.connect(path.absolute().as_uri() + "?mode=ro", uri=True)
    try:
        db.row_factory = sqlite3.Row
        exists = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='transactions'"
        ).fetchone()
        if not exists:
            return []
        return [dict(row) for row in db.execute(
            "SELECT * FROM transactions ORDER BY rowid DESC LIMIT 200"
        )]
    finally:
        db.close()


class AptxDashboard(App):
    """Read-only UI; all native APT operations run off the event loop."""

    TITLE = "aptx — package browser"
    SUB_TITLE = "Read-only dashboard"
    CSS = """
    #query { margin: 1 2; }
    .actions { height: auto; margin: 0 2 1 2; }
    .actions Button { min-width: 12; margin-right: 1; }
    #status { height: auto; margin: 0 2 1 2; }
    #results { padding: 1 2; }
    """
    BINDINGS: ClassVar = [
        ("ctrl+q", "quit", "Quit"),
        ("ctrl+f", "focus_search", "Search"),
        ("ctrl+t", "toggle_theme", "Theme"),
        ("ctrl+r", "refresh", "Refresh"),
    ]

    def __init__(self, backend: Any = None, state_dir: Path | None = None) -> None:
        super().__init__()
        if backend is None:
            from aptx.packages import AptBackend
            backend = AptBackend()
        self.backend = backend
        self.state_dir = state_dir or Path(
            os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))
        ) / "aptx"
        self._last_action = "search"
        self._busy = False

    def compose(self) -> ComposeResult:
        yield Header()
        yield Input(placeholder="Package name or search terms", id="query")
        with Horizontal(classes="actions"):
            yield Button("Search", id="search", variant="primary")
            yield Button("Details", id="show")
            yield Button("Downloads", id="downloads")
            yield Button("Doctor", id="doctor")
        with Horizontal(classes="actions"):
            yield Button("History", id="history")
            yield Button("Config", id="config")
        yield Static("Enter a query and press Enter. Ctrl+T changes theme.", id="status")
        with VerticalScroll():
            yield Static("Download status is local; refresh with Ctrl+R.", id="results",
                         markup=False)
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#query", Input).focus()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        await self.perform("search")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id:
            await self.perform(event.button.id)

    def action_focus_search(self) -> None:
        self.query_one("#query", Input).focus()

    def action_toggle_theme(self) -> None:
        self.theme = "textual-light" if self.theme != "textual-light" else "textual-dark"

    async def action_refresh(self) -> None:
        await self.perform(self._last_action)

    async def perform(self, action: str) -> None:
        if self._busy:
            return
        query = self.query_one("#query", Input).value.strip()
        status = self.query_one("#status", Static)
        if action in {"search", "show"} and not query:
            status.update("Enter a package name or search terms first.")
            return
        self._last_action = action
        self._busy = True
        status.update(f"Loading {action}…")
        try:
            result: Any
            if action == "downloads":
                result = await asyncio.to_thread(read_downloads, self.state_dir)
            elif action == "history":
                result = await asyncio.to_thread(read_history, self.state_dir)
            elif action == "config":
                result = {
                    "state_directory": str(self.state_dir),
                    "cache_directory": str(Path(os.environ.get(
                        "XDG_CACHE_HOME", str(Path.home() / ".cache")
                    )) / "aptx"),
                    "theme": self.theme,
                    "apt_configuration": "APT system configuration remains authoritative",
                }
            elif action == "doctor":
                result = await asyncio.to_thread(self.backend.doctor)
            elif action in {"search", "show"}:
                result = await asyncio.to_thread(self.backend.read, action, [query])
            else:
                raise ValueError("Unsupported dashboard action")
            if isinstance(result, dict) and "stdout" in result:
                rendered = result["stdout"]
                if result.get("stderr"):
                    rendered += "\n" + result["stderr"]
                if not rendered.strip():
                    rendered = "No matching results."
            else:
                rendered = json.dumps(result, indent=2, ensure_ascii=False, default=str)
            self.query_one("#results", Static).update(rendered)
            status.update(f"{action.capitalize()} complete. Ctrl+R refreshes this view.")
        except Exception as exc:  # noqa: BLE001 -- keep UI alive and show backend failure
            status.update("Operation failed; see details below.")
            self.query_one("#results", Static).update(str(exc))
        finally:
            self._busy = False


def run_dashboard() -> None:
    AptxDashboard().run()
