#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
stage=$(mktemp -d /tmp/aptx-deb.XXXXXX)
trap 'rm -rf "$stage"' EXIT
mkdir -p "$stage/DEBIAN" "$stage/usr/lib/python3/dist-packages/aptx" "$stage/usr/bin" dist
cp aptx/*.py "$stage/usr/lib/python3/dist-packages/aptx/"
cat > "$stage/DEBIAN/control" <<'CONTROL'
Package: aptx
Version: 0.1.0
Section: admin
Priority: optional
Architecture: all
Maintainer: aptx contributors <aptx@localhost>
Depends: python3 (>= 3.11), python3 (<< 3.14), python3-apt, python3-twisted (>= 24.11), python3-rich (>= 13.9), python3-textual (>= 1.0), python3-typer (>= 0.15), sudo
Description: Native APT frontend with verified asynchronous downloads
 Candidate build. Distribution dependency and installation matrix pending.
CONTROL
cat > "$stage/usr/bin/aptx" <<'LAUNCHER'
#!/usr/bin/python3
from aptx.__main__ import main
main()
LAUNCHER
chmod 755 "$stage/usr/bin/aptx"
SOURCE_DATE_EPOCH=${SOURCE_DATE_EPOCH:-1793332800} export SOURCE_DATE_EPOCH
scripts/quiet-run.sh dpkg-deb --root-owner-group --build "$stage" dist/aptx_0.1.0_all.deb
