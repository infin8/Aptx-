# Local development installation

Use the distribution Python so python-apt matches its ABI (Python 3.11–3.13).
From this directory run `scripts/bootstrap.sh`, then `.venv/bin/aptx --help`.
`.venv/bin/aptx` opens the read-only dashboard. `.venv/bin/aptx --json doctor`
checks native APT availability. User state and cache follow XDG directories.

Package transactions use native APT acquisition, signatures, dependency resolution,
and locks. They are not accelerated by the custom downloader. Inspect a plan with
`aptx --json install hello --dry-run`. Actual changes require confirmation and sudo;
`--yes` skips confirmation but never authentication. Never test changes on a host
that you cannot restore. `aptx download hello` only downloads into the current directory.

`aptx fetch URL SHA256 SIZE` uses pooled Twisted downloads and verifies the supplied
size and digest. A caller-supplied digest does not establish repository authenticity.
Use metadata obtained from an authenticated trusted source. `aptx downloads` lists IDs;
`aptx resume ID` safely restarts a saved transfer. `aptx history` shows operations
requested through this frontend, not all system APT history.

Build: `scripts/quiet-run.sh .venv/bin/python -m build`, then `scripts/build-deb.sh`.
The candidate `.deb` declares minimum dependency versions required by the specification.
Older distro repositories may not provide them; do not force dependency installation.
The development venv can use PyPI UI/network libraries and distro python-apt.
The Debian package is not release-certified until the installation matrix passes.

The dashboard currently provides read-only search, details, download state, history,
configuration and diagnostics. Live cross-process download controls, repository/key
editing, and pin editing are not implemented. `repo`/`pin` inspect native policy.
Do not interpret these inspection commands as configuration editors.

For reproducible local dependency versions, install `requirements.lock` into the
system-site-packages venv before editable installation. That lock records this local
Ubuntu/Python environment; it does not establish compatibility with other distributions.
The native final APT confirmation remains visible for interactive package changes.
An explicit `--yes` accepts native APT's current resolution, which may differ from an
earlier preview if repository or installed-package state changed.
