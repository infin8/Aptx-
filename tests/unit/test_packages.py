"""All native subprocesses are mocked: these tests never mutate the host."""
import subprocess
from unittest.mock import patch

import pytest

from aptx.packages import AptBackend, AptError
from aptx.security import SecurityError, safe_environment, validate_packages


@pytest.fixture(autouse=True)
def native_boundary():
    with patch("aptx.packages.subprocess.run") as run, \
            patch("aptx.packages.native_binary", side_effect=lambda n: f"/usr/bin/{n}"), \
            patch("aptx.security.native_binary", side_effect=lambda n: f"/usr/bin/{n}"), \
            patch("aptx.security.os.geteuid", return_value=1000):
        run.return_value = subprocess.CompletedProcess([], 0, "native output", "")
        yield run


@pytest.mark.parametrize("value", ["--allow-unauthenticated", "-oAPT::Get::AllowUnauthenticated=true",
                                   "./evil.deb", "/tmp/evil.deb", "pkg;id", "pkg\nother", "pkg/unstable", ""])
def test_reject_option_and_path_injection(value, native_boundary):
    with pytest.raises(SecurityError):
        AptBackend().execute("install", [value], yes=True)
    native_boundary.assert_not_called()


def test_version_and_architecture():
    assert validate_packages(["libc6:amd64=2.36-9+deb12u10", "g++"]) == [
        "libc6:amd64=2.36-9+deb12u10", "g++"]


def test_mutation_uses_narrow_sudo(native_boundary):
    AptBackend().execute("install", ["vim"], yes=True, noninteractive=True)
    args, kwargs = native_boundary.call_args
    assert args[0] == ["/usr/bin/sudo", "-n", "--preserve-env=DEBIAN_FRONTEND", "--", "/usr/bin/apt-get",
                       "--assume-yes", "install", "vim"]
    assert kwargs["shell"] is False
    assert kwargs["env"]["DEBIAN_FRONTEND"] == "noninteractive"


def test_download_never_elevates(native_boundary):
    AptBackend().execute("download", ["vim"])
    assert native_boundary.call_args.args[0] == ["/usr/bin/apt-get", "download", "vim"]
    assert native_boundary.call_args.kwargs["capture_output"] is True


def test_interactive_native_confirmation_is_visible(native_boundary):
    native_boundary.return_value = subprocess.CompletedProcess([], 0, None, None)
    result = AptBackend().execute("install", ["vim"])
    assert native_boundary.call_args.kwargs["capture_output"] is False
    assert "--assume-yes" not in native_boundary.call_args.args[0]
    assert result["stdout"] == result["stderr"] == ""


def test_interactive_failure_handles_inherited_streams(native_boundary):
    native_boundary.return_value = subprocess.CompletedProcess([], 100, None, None)
    with pytest.raises(AptError) as failure:
        AptBackend().execute("install", ["vim"])
    assert failure.value.code == 6


def test_explicit_yes_captures_native_output(native_boundary):
    AptBackend().execute("install", ["vim"], yes=True)
    assert native_boundary.call_args.kwargs["capture_output"] is True


def test_noninteractive_requires_confirmation(native_boundary):
    with pytest.raises(SecurityError):
        AptBackend().execute("update", [], noninteractive=True)
    native_boundary.assert_not_called()


def test_plan_only_simulates(native_boundary):
    with patch("aptx.packages.importlib.import_module", side_effect=ImportError("optional")):
        plan = AptBackend().plan("install", ["vim"])
    assert plan["dry_run"] is True
    assert native_boundary.call_args.args[0] == ["/usr/bin/apt-get", "--simulate", "install", "vim"]
    assert plan["warnings"]


def test_update_plan_never_updates(native_boundary):
    AptBackend().plan("update", [])
    native_boundary.assert_not_called()


def test_read_search_never_elevates(native_boundary):
    AptBackend().read("search", ["text editor"])
    assert native_boundary.call_args.args[0] == ["/usr/bin/apt-cache", "search", "--", "text editor"]


def test_failed_native_operation(native_boundary):
    native_boundary.return_value = subprocess.CompletedProcess([], 100, "", "Could not get lock")
    with pytest.raises(AptError) as failure:
        AptBackend().execute("update", [], yes=True)
    assert failure.value.code == 6
    assert failure.value.details["returncode"] == 100


def test_environment_drops_injection(monkeypatch):
    monkeypatch.setenv("APT_CONFIG", "/tmp/attacker.conf")
    monkeypatch.setenv("LD_PRELOAD", "/tmp/attacker.so")
    assert "APT_CONFIG" not in safe_environment()
    assert "LD_PRELOAD" not in safe_environment()
