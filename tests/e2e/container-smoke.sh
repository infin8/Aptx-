#!/bin/sh
set -eu
test -f /.dockerenv || { echo 'Refusing package mutations outside Docker'; exit 8; }
export DEBIAN_FRONTEND=noninteractive
export PIP_DISABLE_PIP_VERSION_CHECK=1
export PIP_PROGRESS_BAR=off
apt-get -qq update
apt-get -qq -y install python3 python3-venv python3-apt ca-certificates
cp -r /src /tmp/aptx
rm -rf /tmp/aptx/.venv /tmp/aptx/dist /tmp/aptx/build
python3 -m venv --system-site-packages /tmp/smoke-venv
/tmp/smoke-venv/bin/python -m pip install --quiet --no-cache-dir /tmp/aptx
/tmp/smoke-venv/bin/python -c 'import apt; print("python-apt import PASS")'
/tmp/smoke-venv/bin/aptx --json doctor
/tmp/smoke-venv/bin/aptx --json install hello --dry-run
if dpkg-query -W -f='${Status}' hello 2>/dev/null | grep -q 'install ok installed'; then
    echo 'Dry run unexpectedly installed hello'; exit 1
fi
/tmp/smoke-venv/bin/aptx --json install hello --yes --noninteractive
dpkg-query -W -f='${Status}' hello | grep -q 'install ok installed'
/tmp/smoke-venv/bin/aptx --json remove hello --yes --noninteractive
if dpkg-query -W -f='${Status}' hello 2>/dev/null | grep -q 'install ok installed'; then
    echo 'hello remained installed'; exit 1
fi
echo 'PASS: wheel install, distro python-apt, doctor, dry-run, signed-repository install/remove'
