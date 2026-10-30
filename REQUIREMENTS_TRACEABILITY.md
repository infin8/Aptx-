# Requirements traceability

| Requirement | Implementation / local evidence | Release gap |
| --- | --- | --- |
| R01 | pyproject.toml, scripts/build-deb.sh | Distro installation matrix |
| R02 | aptx/downloader.py, test_ranges.py | Broader HTTP failure matrix |
| R03 | aptx/persistence.py, test_resume.py, test_state.py | Crash VM scenarios; multipart restart only |
| R04 | aptx/packages.py delegates native trust | Signed local repo E2E not run |
| R05 | aptx/cli.py, test_cli.py | Repo/pin edits missing; config read-only |
| R06 | aptx/security.py, test_packages.py | Real sudo/lock matrix |
| R07 | aptx/tui.py, test_ui.py | Live dashboard transfer controls |
| R08 | aptx/scheduler.py, downloader/cache | Adaptive throttling/mirrors |
| R09 | Argument/cache/range adversarial tests | Complete hostile-input and privilege audit |
| R10 | Unit/integration tests and container script | Registry connectivity; Mint VM |
| R11 | benchmarks/run.py, evidence/local/benchmark.json | Warm/cold and distro matrix |
| R12 | Build tooling, docs, component audits | Independent release approval |
