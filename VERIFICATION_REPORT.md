# Verification report

Environment: Ubuntu 24.04.3, Python 3.12.3; distribution python-apt available.
Exact Python dependency versions are recorded in requirements.lock.

Local checks: Ruff, mypy, **48 passing unit/integration tests**, wheel/sdist generation and candidate
Debian package generation. Final captured output is in evidence/local/verification.log.
Tests cover option injection and sanitized native commands, explicit confirmation,
dry run, CLI JSON, hostname/reactor startup, actual local HTTP ranges and fallback,
digest mismatch, resume, transfer controls, secure cache files and headless Textual.
Native mutations in local tests are mocked; no installed host package was changed.

Real network benchmark: evidence/local/benchmark.json contains five native and five
aptx successful transfers of Ubuntu's trusted hello candidate. Native median 11.218s;
aptx median 13.938s (approximately 24% slower). aptx p95 89.375s shows substantial
network/retry variability. Raw CPU, peak RSS and retained disk measurements and their
limitations are included. No speedup claim is made. The pre-fix failed benchmark is
retained as evidence/local/benchmark-before-reactor-start.json; it exposed missing
Twisted reactor startup, now fixed and covered by a hostname CLI regression test.

Independent reviews: evidence/local/SECURITY_REVIEW.md and BACKEND_REVIEW.md.
Follow-up fixes include safe hardlink handling, callback failure propagation, reactor
startup, integrity exit codes, JSON parse failures and visible native APT prompts.
Remaining scope gaps and preview revalidation limits are in COMPLETION_REPORT.md.

Distro matrix: BLOCKED by Docker registry TLS/TCP failures before any container
execution. See evidence/matrix/RESULTS.md and per-image logs. No cross-distro success
or Debian installation success is claimed.
