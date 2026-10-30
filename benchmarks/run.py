"""Compare native APT acquisition and aptx acquisition against trusted metadata."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import os
import signal
import statistics
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


@dataclass(frozen=True)
class TrustedSpec:
    package: str
    version: str
    uri: str
    expected_size: int
    sha256: str


def resolve(package: str) -> TrustedSpec:
    from aptx.security import validate_packages
    validate_packages([package])
    if "=" in package:
        raise ValueError("Benchmark selects the current APT candidate; omit a version")
    import apt
    cache = apt.Cache()
    candidate = cache[package].candidate
    if candidate is None:
        raise ValueError("Package has no APT candidate")
    if not candidate.origins or not all(origin.trusted for origin in candidate.origins):
        raise ValueError("Candidate origins must all be trusted by native APT")
    digest = candidate.record.get("SHA256", "")
    if not isinstance(digest, str) or len(digest) != 64 or any(
        c not in "0123456789abcdef" for c in digest
    ):
        raise ValueError("Candidate lacks a valid SHA256 in APT metadata")
    uri = candidate.uri
    if not uri or urlsplit(uri).scheme not in {"http", "https"}:
        raise ValueError("Benchmark requires an HTTP(S) repository")
    if candidate.size <= 0:
        raise ValueError("Candidate has no trusted size")
    return TrustedSpec(package, candidate.version, uri, candidate.size, digest)


def summarize(samples: list[dict]) -> dict:
    successful = [sample for sample in samples if sample["ok"]]
    if not successful:
        return {"successful_runs": 0, "failed_runs": len(samples)}
    times = sorted(sample["wall_seconds"] for sample in successful)
    return {
        "successful_runs": len(successful), "failed_runs": len(samples) - len(successful),
        "median_seconds": statistics.median(times),
        "p95_seconds": times[math.ceil(0.95 * len(times)) - 1],
        "median_user_seconds": statistics.median(s["user_seconds"] for s in successful),
        "median_system_seconds": statistics.median(s["system_seconds"] for s in successful),
        "maximum_peak_rss_kib": max(s["peak_rss_kib"] for s in successful),
        "median_disk_allocated_bytes": statistics.median(
            s["disk_allocated_bytes"] for s in successful),
    }


def measure(command: list[str], directory: Path, timeout: float = 120) -> dict:
    """wait4 reports resource use for the reaped process on supported Linux hosts."""
    started = time.perf_counter()
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        process = subprocess.Popen(command, cwd=directory, stdout=stdout, stderr=stderr,
                                   start_new_session=True)
        timed_out = False
        while True:
            pid, status, usage = os.wait4(process.pid, os.WNOHANG)
            if pid:
                break
            if time.perf_counter() - started > timeout:
                os.killpg(process.pid, signal.SIGKILL)
                _, status, usage = os.wait4(process.pid, 0)
                timed_out = True
                break
            time.sleep(0.005)
        elapsed = time.perf_counter() - started
        process.returncode = os.waitstatus_to_exitcode(status)
        stderr.seek(0, os.SEEK_END)
        stderr.seek(max(0, stderr.tell() - 4000))
        error = stderr.read().decode(errors="replace")
    files = [path for path in directory.rglob("*") if path.is_file()]
    return {
        "ok": process.returncode == 0 and not timed_out,
        "returncode": process.returncode, "timed_out": timed_out,
        "wall_seconds": elapsed, "user_seconds": usage.ru_utime,
        "system_seconds": usage.ru_stime, "peak_rss_kib": usage.ru_maxrss,
        "disk_logical_bytes": sum(path.stat().st_size for path in files),
        "disk_allocated_bytes": sum(path.stat().st_blocks * 512 for path in files),
        "error": error if process.returncode else None,
    }


def verify(directory: Path, spec: TrustedSpec, engine: str) -> bool:
    candidates = list(directory.glob("*.deb")) if engine == "apt" else [
        directory / "cache" / spec.sha256]
    if len(candidates) != 1 or not candidates[0].is_file():
        return False
    path = candidates[0]
    if path.stat().st_size != spec.expected_size:
        return False
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest() == spec.sha256


def run_benchmark(spec: TrustedSpec, repetitions: int) -> dict:
    from aptx.security import native_binary
    if repetitions < 1 or repetitions > 100:
        raise ValueError("Repetitions must be between 1 and 100")
    report: dict[str, Any] = {"schema_version": 1, "package": asdict(spec), "repetitions": repetitions,
              "samples": {"apt": [], "aptx": []}, "limitations": [
        "Download-only comparison; no package installation or host cache changes.",
        "Fresh output/cache directories each run; kernel, DNS, and remote caches remain warm.",
        "Alternating execution order reduces but does not eliminate network/order effects.",
        "Wall time includes process startup, rounded by approximately 5ms polling.",
        "CPU and peak RSS use Linux wait4 child accounting; peak RSS is not summed concurrent RAM.",
        "Peak RSS may include inherited memory before exec; it is not steady-state application RAM.",
        "Disk bytes are final retained files, including aptx SQLite; not total I/O traffic.",
        "APT metadata resolution and post-run benchmark hash verification are outside timings.",
        "APT and aptx use their own acquisition defaults; this is not a transport-isolation study.",
        "p95 is nearest rank and unstable for small sample counts.",
    ]}
    with tempfile.TemporaryDirectory(prefix="aptx-benchmark-") as work:
        for repetition in range(repetitions):
            order = ("apt", "aptx") if repetition % 2 == 0 else ("aptx", "apt")
            for engine in order:
                directory = Path(work) / f"{repetition}-{engine}"
                directory.mkdir()
                if engine == "apt":
                    command = [native_binary("apt-get"), "-q", "-o", "Acquire::Retries=0",
                               "-o", "Acquire::http::Timeout=30", "-o", "Acquire::https::Timeout=30",
                               "download", f"{spec.package}={spec.version}"]
                else:
                    command = [sys.executable, str(Path(__file__).absolute()), "--worker",
                               json.dumps(asdict(spec)), "--directory", str(directory)]
                sample = measure(command, directory)
                sample["repetition"] = repetition + 1
                if sample["ok"] and not verify(directory, spec, engine):
                    sample["ok"] = False
                    sample["error"] = "Downloaded bytes did not match trusted size and SHA256"
                report["samples"][engine].append(sample)
    report["summary"] = {key: summarize(samples) for key, samples in report["samples"].items()}
    report["ok"] = all(s["ok"] for samples in report["samples"].values() for s in samples)
    if report["ok"]:
        report["aptx_to_apt_median_ratio"] = (report["summary"]["aptx"]["median_seconds"] /
                                               report["summary"]["apt"]["median_seconds"])
    return report


def worker(raw_spec: str, directory: Path) -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    from twisted.internet import asyncioreactor
    asyncioreactor.install(loop)
    from twisted.internet import reactor
    active_reactor: Any = reactor
    active_reactor.startRunning(installSignalHandlers=False)
    from aptx.downloader import DownloadManager, DownloadSpec

    async def transfer():
        manager = DownloadManager(directory / "state", directory / "cache")
        try:
            await manager.download(DownloadSpec(**json.loads(raw_spec)))
        finally:
            await manager.close()
    try:
        loop.run_until_complete(transfer())
    finally:
        active_reactor.fireSystemEvent("shutdown")
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", default="hello")
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--worker", help=argparse.SUPPRESS)
    parser.add_argument("--directory", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        worker(args.worker, args.directory)
        return 0
    try:
        if not 1 <= args.repetitions <= 100:
            raise ValueError("Repetitions must be between 1 and 100")
        report = run_benchmark(resolve(args.package), args.repetitions)
    except Exception as exc:  # noqa: BLE001 -- emit machine-readable benchmark failure
        report = {"schema_version": 1, "ok": False, "error": str(exc)}
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
