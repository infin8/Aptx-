# Mandatory goals

Completion = PASS / 12 × 100. Zero goals is never complete. All mandatory goals and applicable release gates must PASS. Local implementation and evidence exist; supported-matrix gates remain unverified. Evidence under evidence/Gxx/.

| ID | Expected measurable outcome | Owner | Dependency | Test command | Expected output | Evidence | Status |
|---|---|---|---|---|---|---|---|
| G01 | Installable on distro matrix; binary PASS on supported matrix | DEVOPS | T11 | `VM install .deb && aptx --help` | Exit 0 and recorded assertions | `evidence/G01/` | UNVERIFIED |
| G02 | Twisted real HTTP transfers and multipart fallback; binary PASS on supported matrix | TWISTED | T03 | `pytest tests/integration/test_ranges.py` | Exit 0 and recorded assertions | `evidence/G02/` | UNVERIFIED |
| G03 | Resumes crash safely and verifies digest; binary PASS on supported matrix | DATABASE | T04 | `pytest tests/integration/test_resume.py` | Exit 0 and recorded assertions | `evidence/G03/` | UNVERIFIED |
| G04 | APT trust and native dependency semantics; binary PASS on supported matrix | DEBIAN | T05 | `pytest tests/e2e/test_signed_repo.py` | Exit 0 and recorded assertions | `evidence/G04/` | UNVERIFIED |
| G05 | All package-management commands functional; binary PASS on supported matrix | DEBIAN | T05 | `pytest tests/e2e/test_commands.py` | Exit 0 and recorded assertions | `evidence/G05/` | UNVERIFIED |
| G06 | Integrated sudo and native locks safe; binary PASS on supported matrix | SECURITY | T06 | `pytest tests/e2e/test_privileges.py` | Exit 0 and recorded assertions | `evidence/G06/` | UNVERIFIED |
| G07 | Rich CLI and Textual TUI work; binary PASS on supported matrix | FRONTEND | T07 | `pytest tests/integration/test_ui.py` | Exit 0 and recorded assertions | `evidence/G07/` | UNVERIFIED |
| G08 | Adaptive scheduler and cache safe; binary PASS on supported matrix | OPTIMIZATION | T08 | `pytest tests/integration/test_scheduler.py` | Exit 0 and recorded assertions | `evidence/G08/` | UNVERIFIED |
| G09 | Security adversarial suite clean; binary PASS on supported matrix | SECURITY | T09 | `pytest tests/security` | Exit 0 and recorded assertions | `evidence/G09/` | UNVERIFIED |
| G10 | Cross-distro tests pass; binary PASS on supported matrix | QA | T10 | `scripts/test.sh --vm-matrix` | Exit 0 and recorded assertions | `evidence/G10/` | UNVERIFIED |
| G11 | Real comparative benchmarks published; binary PASS on supported matrix | PERFORMANCE | T10 | `python -m benchmarks.run --repetitions 5` | Exit 0 and recorded assertions | `evidence/G11/` | UNVERIFIED |
| G12 | Artifacts, docs, independent audit pass; binary PASS on supported matrix | RELEASE_AUDITOR | T12 | `scripts/audit.sh` | Exit 0 and recorded assertions | `evidence/G12/` | UNVERIFIED |
