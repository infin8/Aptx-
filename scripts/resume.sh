#!/bin/sh
set -eu
git status --short || true
git log -1 --oneline || true
cat project-management/PROGRESS.md
cat operations/RESUME.md
