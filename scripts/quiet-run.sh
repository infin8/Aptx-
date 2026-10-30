#!/bin/sh
set -u
log=$(mktemp /tmp/aptx-command.XXXXXX.log)
"$@" >"$log" 2>&1
status=$?
if [ "$status" -eq 0 ]; then
  echo "PASS: $* (log: $log)"
else
  echo "FAIL ($status): $* (log: $log)"
  tail -n 150 "$log"
fi
exit "$status"
