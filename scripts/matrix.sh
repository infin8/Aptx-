#!/bin/sh
set -u
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
mkdir -p "$root/evidence/matrix"
status=0
for image in debian:12-slim debian:13-slim ubuntu:24.04; do
    label=$(printf '%s' "$image" | tr ':/' '__')
    log="$root/evidence/matrix/$label.log"
    if docker run --rm --pull=missing --mount "type=bind,source=$root,target=/src,readonly" "$image" sh /src/tests/e2e/container-smoke.sh >"$log" 2>&1; then
        printf 'PASS %s (evidence: %s)\n' "$image" "$log"
    else
        result=$?
        printf 'FAIL %s exit=%s (evidence: %s)\n' "$image" "$result" "$log"
        tail -n 30 "$log"
        status=1
    fi
done
exit "$status"
