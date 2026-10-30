# Independent security review

Date: 2026-10-30. Reviewer: apt_backend specialist reviewing other authors' CLI,
downloader, scheduler, and persistence. The reviewer implemented the native backend;
this report does **not** independently certify that backend.

## Scope and evidence

Inspected `aptx/cli.py`, `aptx/__main__.py`, `aptx/downloader.py`,
`aptx/persistence.py`, `aptx/scheduler.py`, and corresponding tests. Ran:

`sh scripts/quiet-run.sh .venv/bin/python -m pytest -q tests/unit/test_state.py tests/unit/test_cli.py tests/integration/test_ranges.py tests/integration/test_resume.py`

Result: **16 passed in 11.07s**, log `/tmp/aptx-command.uIMmP0.log`.
Additionally independently exercised a hardlink to an 11-byte victim and an HTTP
body writer raising `OSError`: the victim remained unchanged; the deferred failed
once and the producer connection closed. No host package transactions were run.

## Findings and remediation verified

1. **High, fixed:** `open_private` originally opened with `O_TRUNC` before checking
   regular-file type, owner and link count. A rejected hardlink could lose victim
   contents. It now validates the descriptor before `ftruncate`; independent
   temporary-file reproduction confirmed preservation.
2. **Medium, fixed:** disk-write exceptions escaped the Twisted body callback.
   The callback now errbacks its deferred and closes its producer; independently
   checked with a simulated disk-full exception.
3. **Medium, fixed for cooperating processes:** concurrent managers previously
   shared deterministic partial paths without a process lock. A digest-scoped
   nonblocking `flock` in the cache now protects acquisition and publication.
4. **Medium, fixed by inspection:** first-value-only handling allowed ambiguous
   duplicate range/encoding/length headers. Duplicate values now yield a rejected
   sentinel. Ranges must match exact requested offsets, total length, and validator;
   ETags used for resumption must be quoted and strong. Body writes enforce the
   expected remaining size, including when Content-Length is absent.
5. **Low, fixed by inspection:** CLI fetch classified integrity failures as network
   failures; it now returns integrity code 5. Entrypoint usage errors in JSON mode
   now use the documented envelope rather than only Click's text output.

## Trust and remaining limits

`fetch` explicitly labels its trust as a caller-supplied digest. Such data does not
become an authenticated APT package and is not fed into privileged package
installation. Native package acquisition remains separate. JSON transaction mode
requires explicit approval; read-only and dry-run tests prove no execute callback.

Cache directories are private and filesystem opens reject symlinks. These controls
are not a complete defense against another malicious process running as the same
UID: ancestor checks and verify-then-publish paths are not all descriptor-relative.
The process lock coordinates conforming clients, not arbitrary hostile same-UID
writers. No adversarial symlink-race stress test or resource-exhaustion soak test was
performed. HTTP transfer sizes and operation timeouts are bounded, but callers can
request arbitrarily large expected sizes; no user-configurable disk quota exists.

Repository trust edits, policy pin writes, supported-distribution privilege flows,
crash consistency, and release-wide dependency auditing are outside this independent
review. This limited review is **not a release certification**.

## Integration follow-up

CLI startup now starts the asyncio reactor, verified with a subprocess hostname HTTP
regression. CLI integrity failures use exit 5; parser errors in --json mode return the
JSON envelope. Native interactive prompts are visible. Final local verification is
captured separately in evidence/local/verification.log. This remains a component review,
not full release approval.
