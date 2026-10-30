"""Proposed aptx service contracts; implement concrete classes in aptx/.
These protocols are not an executable application.
"""
from dataclasses import dataclass
from typing import Protocol, Literal

@dataclass(frozen=True)
class DownloadSpec:
    package: str
    version: str
    uri: str
    expected_size: int
    sha256: str
    sha512: str | None = None

@dataclass(frozen=True)
class Progress:
    download_id: str
    completed_bytes: int
    total_bytes: int
    bytes_per_second: float
    active_connections: int
    status: Literal['queued','downloading','paused','verifying','complete','failed']

class AptAdapter(Protocol):
    def plan(self, action: str, packages: list[str], dry_run: bool = True) -> object: ...

class DownloadManager(Protocol):
    async def download(self, spec: DownloadSpec) -> str: ...
    async def pause(self, download_id: str) -> None: ...
    async def resume(self, download_id: str) -> None: ...
    async def cancel(self, download_id: str) -> None: ...

class TransactionRunner(Protocol):
    async def execute(self, approved_plan: object, noninteractive: bool = False) -> object: ...
