# Phase 10: Tests and regression
Owner: ORCHESTRATOR; supporting specialists as mapped in TASK_REGISTER.csv.

Entry: preceding phase gate VERIFIED or explicitly independent READY work. Inspect git, requirements, contracts and blockers.
Actions: select mapped tasks, implement actual code with exclusive ownership, run `scripts/test.sh` and task-specific commands, record outputs in evidence/phase-10/, update task and goal records. For privileged operations use disposable VM only. Never treat skipped tests as PASS.
Exit gate: all phase-specific mandatory checks PASS with command output and review, or mark BLOCKED with cause and safe next step. Checkpoint via scripts/resume.sh.
