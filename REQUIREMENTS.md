# Mandatory product requirements
R01 Installable Python package and Debian .deb on supported Debian-family distributions; `aptx --help` works.
R02 Twisted Agent pooled concurrent HTTP downloads, safe multipart Range, and single-stream fallback.
R03 Crash-safe SQLite checkpoints, restart/resume, hash-verified content-addressed cache.
R04 APT native trust chain: signed Release/InRelease metadata, apt policy, package hash, dependency resolution, version selection and holds.
R05 Commands: install/remove/purge/upgrade/full-upgrade/update/search/show/info/list/autoremove/clean/autoclean/download/resume/downloads/history/hold/unhold/pin/repo/doctor/repair/benchmark/config.
R06 Integrated sudo elevation only for privileged operations; no password storage; lock-aware and noninteractive behavior.
R07 Rich CLI and Textual dashboard: search, details, progress, pause/resume/cancel, history, mirrors, config, theme, shortcuts.
R08 Adaptive concurrency, throttling, mirror selection, retries, caching, dedup and per-host constraints.
R09 Safety: no untrusted package execution, path traversal, metadata downgrade, cross-mirror chunk mixing, or bypassed APT locks.
R10 Automated tests across unit/integration/E2E and isolated VM failure scenarios.
R11 Measured native-APT comparative benchmarks, CPU/RAM/disk metrics, documented unfavorable results.
R12 Build artifacts, install docs, completion evidence, CI, backup/recovery and independent release audit.

Roles: user (read-only search/download), local administrator (authenticated system changes), automation caller (noninteractive explicit policy), auditor (read-only evidence). No remote accounts. Search/download require no elevation; install/remove/update repository metadata when writing system directories requires elevation. `--dry-run` must not mutate packages. `--yes` only skips confirmation, not sudo. Cancel download cleans transient file handles but retains verified chunks; cancel dpkg transaction is best effort and must warn of repair need. Concurrent mutating operations must serialize on native APT/dpkg locks. Mirror switch allowed only after discarding incompatible partial bytes and revalidating trusted expected digest. Never use HTTPS alone as package authenticity proof.
