# aptx

Working development build of a native APT frontend with a Rich CLI, Textual dashboard,
Twisted verified downloads, and SQLite recovery state. **Release status: INCOMPLETE.**

Start with [installation instructions](docs/INSTALL.md). Run `scripts/bootstrap.sh`,
then `.venv/bin/aptx --help` or `.venv/bin/aptx --json doctor`.
See [verification](VERIFICATION_REPORT.md), [completion status](COMPLETION_REPORT.md),
and [known limitations](docs/INSTALL.md) before use.

## Original implementation operating manual

**START HERE:** Read README.md, AGENTS.md, BUILD_START.md, REQUIREMENTS.md, GOALS.md, contracts/, playbooks/, project-management/ and git status. Preserve verified work. Select dependency-ready tasks; implement real code, integrate, test, measure, repair, and repeat until every mandatory goal and release gate passes or a genuine blocker is documented.

## Product
aptx is a Python 3.11+ APT-compatible frontend for Debian 12/13, Ubuntu 24.04 LTS and Linux Mint 22.x; additional releases are best effort. Twisted HTTP/1.1 downloads, Rich CLI, Textual dashboard, python-apt for native policy/dependency resolution, APT/dpkg for authoritative transactions. Never rewrite the APT dependency solver or repository trust model. Never bypass APT trust checks. Unprivileged downloads; narrow privileged transactions authenticated through sudo. Root operations require explicit confirmation except --yes, which does not bypass authentication.

## Frozen implementation decisions
Python >=3.11,<3.14; Twisted >=24.11,<27; Rich >=13.9,<16; Textual >=1.0,<9; python-apt provided by OS distribution; sqlite3 standard library; Typer >=0.15,<1; httpx only for benchmark harness, not production downloads; pytest, pytest-twisted, pytest-asyncio, hypothesis, ruff, mypy. Exact compatible versions must be locked and tested by Codex in each supported distro. System python-apt requires distro Python; prefer distro Python in Debian package and venv --system-site-packages for development. Packaging via debian/ and pyproject.toml. Use asyncio reactor installed BEFORE any Twisted reactor import; Textual owns asyncio loop; bridge Deferred to Future using asFuture(loop), and await task cancellation safely.

## Build commands (after Codex implements)
```bash
python3 -m venv --system-site-packages .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
python -m ruff check .
python -m mypy aptx
python -m pytest -q tests/unit tests/integration
python -m pytest -q tests/e2e  # disposable VM/container only
python -m build
aptx --help
aptx doctor
```
Do not run package-mutating E2E tests on the host. See scripts/bootstrap.sh, scripts/test.sh and scripts/audit.sh; these scripts are factory gates and must not pretend the app exists.

## Source map
aptx/{cli,tui,core,downloader,scheduler,mirrors,cache,persistence,packages,security,config,utils}; tests/{unit,integration,e2e}; benchmarks; docs; contracts; agents; playbooks; operations; project-management; evidence. `aptx` with no args opens Textual, commands use Rich; --json emits a single documented JSON envelope with stable exit codes.

## Agent delegation
Use native Codex subagents only after verifying supported syntax. Otherwise run sequential specialist prompts from agents/. Freeze contracts before parallel tasks. Exclusive ownership of source files; orchestrator integrates shared files and reviews changes. See AGENTS.md.

## Release/deployment
Build signed/reproducible candidate artifacts in isolated CI, run distro matrix and performance tests, stage privately. No publication, production package changes, spending, or public deployment without explicit approval.

## Recovery
Read operations/RESUME.md and git status; inspect latest evidence and failed gates; reverify changed dependencies; resume READY tasks. A stopped Codex session needs an authorized external supervisor to restart.

## Definition of done
12 mandatory goals in GOALS.md and every applicable gate PASS with measured evidence; independent release audit PASS; no critical defects. Otherwise report INCOMPLETE/BLOCKED/UNVERIFIED.
