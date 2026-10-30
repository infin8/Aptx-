"""APT remains authoritative for resolution, trust checks, and transaction locks."""
import importlib
import os
import subprocess
from pathlib import Path
from typing import Any, ClassVar

from .security import SecurityError, native_binary, privileged, safe_environment, validate_packages


class AptError(RuntimeError):
    def __init__(self, message: str, code: int = 6, details: Any = None) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details


class AptBackend:
    ACTIONS: ClassVar[set[str]] = {"install", "reinstall", "remove", "purge", "upgrade", "full-upgrade",
               "update", "autoremove", "clean", "autoclean", "repair", "hold", "unhold", "download"}
    REQUIRED_PACKAGES: ClassVar[set[str]] = {"install", "reinstall", "remove", "purge", "hold", "unhold", "download"}
    NO_PACKAGES: ClassVar[set[str]] = {"update", "clean", "autoclean", "repair", "full-upgrade"}

    def _run(self, argv: list[str], noninteractive: bool = False,
             capture_output: bool = True) -> dict[str, Any]:
        try:
            result = subprocess.run(argv, shell=False, text=True, capture_output=capture_output,
                                    env=safe_environment(noninteractive), check=False)
        except FileNotFoundError as exc:
            raise AptError(str(exc), 8) from exc
        data = {"command": argv, "returncode": result.returncode,
                "stdout": result.stdout or "", "stderr": result.stderr or ""}
        if result.returncode:
            message = (result.stderr or "").strip() or (result.stdout or "").strip() or "Native APT command failed"
            code = 3 if Path(argv[0]).name == "sudo" and "sudo:" in message else 6
            raise AptError(message, code, data)
        return data

    def _argv(self, action: str, packages: list[str]) -> list[str]:
        if action not in self.ACTIONS:
            raise SecurityError(f"Unsupported package action: {action}")
        packages = validate_packages(packages)
        if action in self.REQUIRED_PACKAGES and not packages:
            raise SecurityError(f"{action} requires at least one package")
        if action in self.NO_PACKAGES and packages:
            raise SecurityError(f"{action} does not accept package names")
        if action in {"hold", "unhold"}:
            if any("=" in p for p in packages):
                raise SecurityError("Hold commands require package names without versions")
            return [native_binary("apt-mark"), action, *packages]
        command = {"full-upgrade": "dist-upgrade", "repair": "install", "reinstall": "install"}.get(action, action)
        options = ["--reinstall"] if action == "reinstall" else ["--fix-broken"] if action == "repair" else []
        return [native_binary("apt-get"), *options, command, *packages]

    def read(self, command: str, packages: list[str]) -> dict[str, Any]:
        if command == "download":
            return self.execute("download", packages)
        if command in {"hold", "hold list"}:
            if packages not in ([], ["list"]):
                raise SecurityError("hold list takes no packages")
            return self._run([native_binary("apt-mark"), "showhold"])
        if command in {"repo", "repo list"}:
            if packages not in ([], ["list"]):
                raise SecurityError("repo list takes no packages")
            return self._run([native_binary("apt-cache"), "policy"])
        if command == "search":
            if not packages or any(not p or p.startswith("-") or "\x00" in p for p in packages):
                raise SecurityError("search requires non-option search terms")
            return self._run([native_binary("apt-cache"), "search", "--", *packages])
        packages = validate_packages(packages)
        if command in {"show", "info"}:
            if not packages:
                raise SecurityError(f"{command} requires a package")
            return self._run([native_binary("apt-cache"), "show", *packages])
        if command == "list":
            return self._run([native_binary("apt"), "list", *packages])
        raise SecurityError(f"Unsupported read command: {command}")

    def plan(self, action: str, packages: list[str], dry_run: bool = True) -> dict[str, Any]:
        argv = self._argv(action, packages)
        data: dict[str, Any] = {"action": action, "packages": packages, "command": argv,
                                "changes": [], "warnings": [], "solver": "apt-get", "dry_run": True}
        if action in {"update", "hold", "unhold", "download"}:
            data["warnings"].append("This action has no dependency simulation; execution uses native APT checks.")
            return data
        data.update(self._run([argv[0], "--simulate", *argv[1:]]))
        if action in {"install", "remove", "purge", "upgrade", "full-upgrade"}:
            try:
                apt = importlib.import_module("apt")
                cache = apt.Cache()
                if action in {"upgrade", "full-upgrade"} and not packages:
                    cache.upgrade(dist_upgrade=action == "full-upgrade")
                else:
                    for spec in packages:
                        name, _, version = spec.partition("=")
                        package = cache[name]
                        if version:
                            package.candidate = package.versions[version]
                        if action in {"remove", "purge"}:
                            package.mark_delete(purge=action == "purge")
                        else:
                            package.mark_install()
                data["changes"] = [{"package": p.name,
                                    "installed_version": p.installed.version if p.installed else None,
                                    "candidate_version": p.candidate.version if p.candidate else None,
                                    "remove": p.marked_delete} for p in cache.get_changes()]
                data["download_size"] = cache.required_download
                data["disk_size_change"] = cache.required_space
                data["solver"] = "python-apt + apt-get"
            except (ImportError, KeyError, AttributeError, SystemError) as exc:
                data["warnings"].append(f"Structured python-apt plan unavailable: {exc}")
        return data

    def execute(self, action: str, packages: list[str], yes: bool = False,
                noninteractive: bool = False) -> dict[str, Any]:
        """Execute with native resolution and locks, not a frozen preview transaction.

        APT resolves again at execution. Interactive callers see its final prompt;
        explicit yes authorizes the action even if resolution changed since plan().
        """
        argv = self._argv(action, packages)
        if noninteractive and not yes and action != "download":
            raise SecurityError("Noninteractive mutation requires explicit --yes")
        if yes and Path(argv[0]).name == "apt-get" and action != "download":
            argv.insert(1, "--assume-yes")
        if action != "download":
            argv = privileged(argv, noninteractive)
        capture_output = yes or noninteractive or action == "download"
        return self._run(argv, noninteractive, capture_output=capture_output)

    def doctor(self) -> dict[str, Any]:
        binaries: dict[str, str | None] = {}
        for name in ("apt-get", "apt-cache", "apt-mark", "dpkg", "sudo"):
            try:
                binaries[name] = native_binary(name)
            except FileNotFoundError:
                binaries[name] = None
        try:
            importlib.import_module("apt")
            python_apt = True
        except ImportError:
            python_apt = False
        return {"supported": all(binaries[n] for n in ("apt-get", "apt-cache", "dpkg")),
                "binaries": binaries, "python_apt": python_apt, "uid": os.geteuid(),
                "native_locks": True, "trust": "Native APT signature and package verification"}
