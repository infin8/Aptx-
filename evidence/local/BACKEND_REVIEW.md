# Independent backend and CLI review

Reviewer: downloader specialist, reviewing files owned by other contributors.
Scope: read-only inspection of `aptx/packages.py`, `aptx/security.py`, `aptx/cli.py`, `aptx/__main__.py`, their existing unit tests, and API/security requirements. No host package mutation, repository changes, or privilege escalation was performed. This is not a production release certification.

## Findings

1. **HIGH — approved plan is not bound to execution.** `cli.backend_call` obtains/displays `backend.plan`, then invokes `backend.execute(command, packages, yes=True, ...)`. `AptBackend.execute` accepts neither the approved plan nor its digest, performs no comparison/revalidation, and inserts `--assume-yes`. Package state or repository candidates changing during user confirmation or sudo authorization can therefore yield changes that were not shown in the approved plan. Native APT trust and native locking still apply, but they do not establish equivalence to the displayed plan. This fails API_SPEC's requirement to revalidate the approved plan under the native lock. Do not claim this guarantee. A later unlocked simulation comparison would reduce but not close the race; a native transaction plan/lock mechanism or explicit safe scope limitation is needed.

2. **MEDIUM — interactive native output is hidden until completion.** `_run` uses `capture_output=True` for mutating commands while inheriting stdin. Native dpkg/conffile or frontend prompts can wait for input whose accompanying output is hidden. `--assume-yes` is not a universal answer to dpkg configuration prompts. Execution needs an explicit interactive streaming/TTY strategy and a distinct structured-output automation path. Existing tests mock subprocess completion and do not exercise real interactive configuration prompts.

3. **MEDIUM — recovery and error classifications are incomplete.** `_run` maps almost every native failure to code 6, except a sudo string heuristic. A dpkg operation that partially modified the system is not distinguished with API code 7, and acquisition/trust failures are not differentiated as 4/5. No native installed-state recovery report is provided. Existing tests cover lock error classification only.

4. **Scope gap — repository and pin management are read-only.** CLI `repo` and `pin` both expose `apt-cache policy`. There is no repository addition/removal, signing-key scope/fingerprint review, or pin editing. This safely avoids implementing an unsafe privileged editor, but cannot support a claim of full repository/pin management. Current command help accurately states pin editing is unsupported.

5. **Scope gap — structured plans can be unavailable or differ from the native solver.** Python-APT is optional; missing bindings leave `changes=[]` plus a warning and native simulation text. Structured results are generated separately from the authoritative native simulation. They should not be described as an immutable native transaction plan. Existing tests verify fallback warnings and that simulation is read-only, not solver equivalence.

## Positive controls inspected

- Package arguments reject options, shell separators, local paths, and invalid specifications.
- Subprocesses use argv lists with `shell=False`.
- Native executable resolution uses fixed system paths rather than caller PATH.
- Native process environment drops APT_CONFIG and loader injection variables.
- `--yes` does not bypass sudo authentication; noninteractive authorization uses `sudo -n`.
- User downloads do not elevate; native APT remains authoritative for transaction trust and locks.
- JSON/noninteractive mutation without explicit `--yes` is rejected by the CLI.
- Dry-run tests forbid calling execute; native command tests mock all subprocess execution.

## Validation

Command: `./scripts/quiet-run.sh .venv/bin/python -m pytest -q --tb=short tests/unit/test_packages.py tests/unit/test_cli.py`.
Result: PASS (21 tests); log `/tmp/aptx-command.fBXHgS.log`. These are mocked boundary tests; they are not evidence that a real privileged transaction, conffile prompt, race, interrupted dpkg operation, or repository edit has passed.

## Review disposition

Useful guarded native-APT wrapper and package-query foundation. Full backend acceptance and production readiness remain blocked on the approved-plan execution guarantee and real disposable-environment transaction/recovery validation. Repository/pin mutation remains explicitly unimplemented.

## Integration follow-up

Interactive native execution now inherits output and retains native APT confirmation;
CLI no longer implicitly adds --assume-yes after its preliminary confirmation.
Explicit --yes retains native automatic resolution semantics. New mocked tests cover
visible prompts and failure handling. Preview-to-execution binding remains a documented
release limitation, not a passing gate.
