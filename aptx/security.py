"""Narrow native-command boundary; caller data is never interpreted by a shell."""
import os
import re
import shutil


class SecurityError(ValueError):
    """An argument cannot safely cross the native command boundary."""


_PACKAGE = re.compile(r"[a-z0-9][a-z0-9+.-]*(?::[a-z0-9][a-z0-9-]*)?(?:=[A-Za-z0-9.+:~_-]+)?\Z")
_BINARIES = {"apt-get", "apt-cache", "apt", "apt-mark", "dpkg", "sudo"}


def validate_packages(packages: list[str]) -> list[str]:
    for package in packages:
        if not isinstance(package, str) or not _PACKAGE.fullmatch(package):
            raise SecurityError(f"Invalid package specification: {package!r}")
    return list(packages)


def native_binary(name: str) -> str:
    if name not in _BINARIES:
        raise SecurityError(f"Native command is not allowed: {name}")
    # Never resolve executables through a caller-controlled PATH.
    path = shutil.which(name, path="/usr/sbin:/usr/bin:/sbin:/bin")
    if path is None:
        raise FileNotFoundError(f"Required native command is unavailable: {name}")
    return path


def safe_environment(noninteractive: bool = False) -> dict[str, str]:
    env = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"}
    if os.environ.get("TERM"):
        env["TERM"] = os.environ["TERM"]
    if noninteractive:
        env["DEBIAN_FRONTEND"] = "noninteractive"
    return env


def privileged(argv: list[str], noninteractive: bool = False) -> list[str]:
    if os.geteuid() == 0:
        return argv
    options = ["-n", "--preserve-env=DEBIAN_FRONTEND"] if noninteractive else []
    return [native_binary("sudo"), *options, "--", *argv]
