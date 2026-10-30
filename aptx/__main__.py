"""Install the asyncio reactor before importing application networking code."""
import asyncio
import importlib
import json
import sys
from typing import cast


def main() -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    from twisted.internet import asyncioreactor
    asyncioreactor.install(loop)
    from twisted.internet import reactor
    installed_reactor = cast(asyncioreactor.AsyncioSelectorReactor, reactor)
    installed_reactor.startRunning(installSignalHandlers=False)
    try:
        click = importlib.import_module("typer._click.exceptions")
    except ModuleNotFoundError:
        click = importlib.import_module("click")

    from typer import Abort

    from aptx.cli import app
    try:
        result = app(standalone_mode=False)
        if isinstance(result, int) and result:
            raise SystemExit(result)
    except (click.ClickException, Abort, KeyboardInterrupt) as exc:
        code = exc.exit_code if isinstance(exc, click.ClickException) else 130
        if "--json" in sys.argv:
            print(json.dumps({"schema_version": 1, "ok": False, "command": "usage",
                              "data": None, "error": {"code": code, "message": str(exc),
                                                      "details": None}}))
        elif isinstance(exc, click.ClickException):
            exc.show()
        raise SystemExit(code) from exc
    finally:
        installed_reactor.fireSystemEvent("shutdown")
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()


if __name__ == "__main__":
    main()
