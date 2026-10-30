"""Bound concurrent requests globally and per origin."""
import asyncio
from contextlib import asynccontextmanager
from urllib.parse import urlsplit


class Scheduler:
    def __init__(self, global_limit=8, per_host_limit=2):
        if global_limit < 1 or per_host_limit < 1:
            raise ValueError('Connection limits must be positive')
        self.global_slots = asyncio.Semaphore(global_limit)
        self.per_host_limit = per_host_limit
        self.hosts = {}

    @asynccontextmanager
    async def slot(self, uri):
        origin = urlsplit(uri).netloc
        host = self.hosts.setdefault(origin, asyncio.Semaphore(self.per_host_limit))
        async with host, self.global_slots:
            yield
