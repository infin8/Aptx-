# Disposable distro matrix attempt

Date: 2026-10-30. Command: `sh scripts/matrix.sh` (exit 1).
Docker daemon was reachable; none of the target images existed locally.

| Target | Result | Evidence |
| --- | --- | --- |
| Debian 12 slim | BLOCKED before container creation: registry TLS handshake timeout, Docker exit 125 | `debian_12-slim.log` |
| Debian 13 slim | BLOCKED before container creation: image layer TCP read timeout, Docker exit 125 | `debian_13-slim.log` |
| Ubuntu 24.04 | BLOCKED before container creation: image layer connection reset, Docker exit 125 | `ubuntu_24.04.log` |
| Linux Mint 22.x | NOT RUN: no Mint image provisioned | No evidence; Ubuntu is not Mint coverage |

No native package mutation or wheel install ran in these target images. No host
package mutation ran. Distribution compatibility and `.deb` dependency compatibility
remain unverified; infrastructure failures do not demonstrate package failure or
success.

The reproducible smoke script mounts source read-only, copies it into the disposable
container, installs distro Python/venv/python-apt from signed repositories, builds
and installs the Python project into a venv with system-site-packages, checks native
python-apt integration and doctor, verifies a dry-run does not install `hello`, and
then installs/removes `hello` through the CLI. It refuses package mutation unless
`/.dockerenv` exists. It tests the Python distribution rather than the generated
Debian archive. Rerun after registry connectivity is restored.
