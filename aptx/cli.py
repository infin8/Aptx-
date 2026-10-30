"""Rich CLI with stable JSON results and explicit transaction approval."""
import asyncio
import json
import os
from pathlib import Path
from typing import Any

import typer
from rich.console import Console

app = typer.Typer(invoke_without_command=True, no_args_is_help=False)
console = Console()


def emit(ctx: typer.Context, command: str, data: dict[str, Any] | None = None,
         error: str | None = None, code: int = 0) -> None:
    envelope = {"schema_version": 1, "ok": error is None, "command": command, "data": data,
                "error": None if error is None else {"code": code, "message": error, "details": None}}
    if ctx.obj.get("json"):
        typer.echo(json.dumps(envelope, default=str))
    elif error:
        console.print(f"[red]Error:[/red] {error}")
    elif data:
        if "stdout" in data:
            console.print(data["stdout"], markup=False, end="")
        else:
            console.print_json(json.dumps(data, default=str))
    if code:
        raise typer.Exit(code)


@app.callback()
def entry(ctx: typer.Context, json_output: bool = typer.Option(False, "--json")) -> None:
    """Native APT operations and verified downloads. No command opens the dashboard."""
    ctx.obj = {"json": json_output}
    if ctx.invoked_subcommand is None:
        if json_output:
            emit(ctx, "help", {"commands": [c.name for c in app.registered_commands]})
        else:
            from aptx.tui import run_dashboard
            run_dashboard()


def backend_call(ctx: typer.Context, command: str, packages: list[str], *,
                 mutate: bool = False, yes: bool = False, dry_run: bool = False,
                 noninteractive: bool = False) -> None:
    from aptx.packages import AptBackend
    try:
        backend = AptBackend()
        if mutate:
            plan = backend.plan(command, packages)
            if dry_run:
                emit(ctx, command, plan)
                return
            if not yes:
                if noninteractive or ctx.obj["json"]:
                    emit(ctx, command, error="Explicit --yes required in noninteractive/JSON mode", code=3)
                console.print_json(json.dumps(plan, default=str))
                if not typer.confirm("Authorize this native APT operation?", default=False):
                    emit(ctx, command, error="Operation declined", code=3)
            from aptx.history import record
            record(state_dir(), command, plan, "APPROVED", 0)
            try:
                result = backend.execute(command, packages, yes=yes, noninteractive=noninteractive)
            except Exception as exc:
                record(state_dir(), command, plan, "FAILED", getattr(exc, "code", 9))
                raise
            record(state_dir(), command, plan, "COMPLETE", result.get("returncode", 0))
        else:
            result = backend.read(command, packages)
        rc = result.get("returncode", 0)
        emit(ctx, command, result if not rc else None,
             error=result.get("stderr", "Native command failed") if rc else None,
             code=6 if rc else 0)
    except (typer.Exit, typer.Abort):
        raise
    except Exception as exc:  # noqa: BLE001 -- CLI boundary converts failures to stable envelope
        emit(ctx, command, error=str(exc), code=getattr(exc, "code", 2 if isinstance(exc, ValueError) else 9))


def register_read(name: str) -> None:
    def read(ctx: typer.Context, packages: list[str] = typer.Argument(None)) -> None:  # noqa: B008
        backend_call(ctx, name, packages or [])
    read.__doc__ = f"Query native APT: {name}."
    app.command(name)(read)


def register_action(name: str) -> None:
    def action(ctx: typer.Context, packages: list[str] = typer.Argument(None),  # noqa: B008
               yes: bool = typer.Option(False, "--yes", "-y"),
               dry_run: bool = typer.Option(False, "--dry-run"),
               noninteractive: bool = typer.Option(False, "--noninteractive")) -> None:
        backend_call(ctx, name, packages or [], mutate=True, yes=yes,
                     dry_run=dry_run, noninteractive=noninteractive)
    action.__doc__ = f"Plan and authorize native {name}; --yes still requires sudo authorization."
    app.command(name)(action)


for _name in ("search", "show", "info", "list", "repo", "download"):
    register_read(_name)
for _name in ("install", "remove", "purge", "upgrade", "full-upgrade", "update",
              "autoremove", "clean", "autoclean", "hold", "unhold", "repair"):
    register_action(_name)


@app.command()
def doctor(ctx: typer.Context) -> None:
    """Inspect local APT dependencies without changing the system."""
    from aptx.packages import AptBackend
    emit(ctx, "doctor", AptBackend().doctor())


@app.command()
def config(ctx: typer.Context) -> None:
    """Show resolved user storage paths."""
    emit(ctx, "config", {"state": str(state_dir()), "cache": str(cache_dir()),
                         "acquisition": "native APT for package transactions"})


def state_dir() -> Path:
    return Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "aptx"


def cache_dir() -> Path:
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "aptx"


@app.command("fetch")
def fetch(ctx: typer.Context, uri: str, sha256: str, size: int,
          package: str = "artifact", version: str = "unknown", sha512: str | None = None) -> None:
    """Download against an explicitly supplied digest; this does not establish APT trust."""
    from aptx.downloader import DownloadManager, DownloadSpec, IntegrityError
    try:
        manager = DownloadManager(state_dir(), cache_dir())
        async def transfer() -> str:
            try:
                return await manager.download(DownloadSpec(package, version, uri, size, sha256, sha512))
            finally:
                await manager.close()
        path = asyncio.get_event_loop().run_until_complete(transfer())
        emit(ctx, "fetch", {"path": path, "trust": "caller-supplied digest"})
    except Exception as exc:  # noqa: BLE001 -- CLI boundary converts failures to stable envelope
        emit(ctx, "fetch", error=str(exc), code=5 if isinstance(exc, IntegrityError) else 4)


def state_rows(table: str) -> list[dict[str, Any]]:
    from aptx.persistence import StateStore
    if table not in {"downloads", "transactions"}:
        raise ValueError("Unknown state table")
    store = StateStore(state_dir())
    try:
        exists = store.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                                  (table,)).fetchone()
        if not exists:
            return []
        return [dict(row) for row in store.db.execute(
            f"SELECT * FROM {table} ORDER BY rowid DESC LIMIT 100")]
    finally:
        store.close()


@app.command()
def downloads(ctx: typer.Context) -> None:
    """List the last 100 verified download checkpoints."""
    emit(ctx, "downloads", {"downloads": state_rows("downloads")})


@app.command()
def history(ctx: typer.Context) -> None:
    """List the last 100 aptx native transaction records."""
    emit(ctx, "history", {"transactions": state_rows("transactions")})


@app.command()
def resume(ctx: typer.Context, download_id: str) -> None:
    """Restart a persisted download, revalidating source and final digest."""
    rows = [r for r in state_rows("downloads") if r["id"] == download_id]
    if not rows:
        emit(ctx, "resume", error="Unknown download ID", code=2)
        return
    row = rows[0]
    fetch(ctx, row["uri"], row["expected_sha256"], row["expected_size"],
          sha512=row.get("expected_sha512"))


@app.command()
def pin(ctx: typer.Context) -> None:
    """Inspect native APT pin priorities; editing is not supported."""
    backend_call(ctx, "repo", [])


@app.command()
def benchmark(ctx: typer.Context, package: str = "hello", repetitions: int = 5) -> None:
    """Measure native vs Twisted downloads without installing packages."""
    import subprocess
    import sys
    result = subprocess.run([sys.executable, "-m", "benchmarks.run", "--package", package,
                             "--repetitions", str(repetitions)], capture_output=True, text=True, check=False)
    if result.returncode:
        emit(ctx, "benchmark", error=result.stderr.strip(), code=4)
    else:
        emit(ctx, "benchmark", json.loads(result.stdout))
