"""Bounded Twisted HTTP acquisition with digest verification and safe range resume.

The asyncio reactor must be installed before importing this module.
"""
import asyncio
import fcntl
import hashlib
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from twisted.internet import reactor
from twisted.internet.defer import Deferred
from twisted.internet.protocol import Protocol
from twisted.python.failure import Failure
from twisted.web.client import Agent, HTTPConnectionPool, ResponseDone
from twisted.web.http_headers import Headers

from .persistence import StateStore, VerifiedCache, open_private
from .scheduler import Scheduler


@dataclass(frozen=True)
class DownloadSpec:
    package: str
    version: str
    uri: str
    expected_size: int
    sha256: str
    sha512: str | None = None


class DownloadError(Exception):
    pass


class IntegrityError(DownloadError):
    pass


async def _await(deferred):
    return await deferred.asFuture(asyncio.get_running_loop())


async def _consume(body, gate, timeout):
    """Count transfer timeout only while the user has not paused acquisition."""
    future = body.done.asFuture(asyncio.get_running_loop())
    elapsed = 0.0
    try:
        while True:
            started = asyncio.get_running_loop().time()
            active = gate.is_set()
            try:
                return await asyncio.wait_for(asyncio.shield(future), min(0.25, timeout))
            except TimeoutError:
                if active and gate.is_set():
                    elapsed += asyncio.get_running_loop().time() - started
                if elapsed >= timeout:
                    raise
    finally:
        if not future.done():
            future.cancel()


class _Body(Protocol):
    transport: Any
    def __init__(self, file, remaining, control):
        self.file, self.remaining, self.control = file, remaining, control
        self.done: Deferred[int] = Deferred(self._cancel)
        self.count = 0

    def _cancel(self, _):
        if hasattr(self, 'transport'):
            self.transport.loseConnection()

    def dataReceived(self, data):
        if self.done.called:
            return
        if self.count + len(data) > self.remaining:
            self.done.errback(IntegrityError('Response exceeds trusted size'))
            self.transport.loseConnection()
            return
        try:
            self.file.write(data)
        except OSError as exc:
            self.done.errback(exc)
            self.transport.loseConnection()
            return
        self.count += len(data)
        if not self.control.is_set():
            self.transport.pauseProducing()

    def connectionLost(self, reason: Failure | None = None) -> None:
        if reason is None:
            reason = Failure(Exception('Connection lost'))
        if not self.done.called:
            if reason.check(ResponseDone):
                self.done.callback(self.count)
            else:
                self.done.errback(reason)


class DownloadManager:
    def __init__(self, state_dir: Path, cache_dir: Path, *, timeout=30, retries=2):
        self.store = StateStore(state_dir)
        self.cache = VerifiedCache(cache_dir)
        self.pool = HTTPConnectionPool(reactor, persistent=True)
        self.pool.maxPersistentPerHost = 2
        self.agent = Agent(reactor, pool=self.pool, connectTimeout=timeout)
        self.scheduler = Scheduler()
        self.timeout, self.retries = timeout, retries
        self.tasks: dict[str, Any] = {}
        self.controls: dict[str, asyncio.Event] = {}
        self.bodies: dict[str, _Body] = {}
        self.locks: dict[str, asyncio.Lock] = {}
        self.parallel_threshold = 1024 * 1024

    @staticmethod
    def download_id(spec):
        return hashlib.sha256((spec.uri + '\0' + spec.sha256).encode()).hexdigest()

    async def download(self, spec):
        parsed = urlsplit(spec.uri)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username:
            raise ValueError('Expected an HTTP(S) URI without credentials')
        if spec.expected_size < 0:
            raise ValueError('Expected size must be nonnegative')
        target = self.cache.path(spec.sha256)
        if spec.sha512 is not None and not re.fullmatch('[0-9a-f]{128}', spec.sha512):
            raise ValueError('Invalid SHA512')
        key = self.download_id(spec)
        # Serialize same-manager cache publication and avoid duplicate partial writers.
        async with self.locks.setdefault(spec.sha256, asyncio.Lock()):
            if await asyncio.to_thread(self.cache.verify, target, spec):
                self.store.checkpoint(key, spec, 'COMPLETE', spec.expected_size)
                return str(target)
            lock_file = open_private(self.cache.directory / (spec.sha256 + '.lock'), append=True)
            try:
                fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                lock_file.close()
                raise DownloadError('This blob is already being downloaded by another process')
            self.tasks[key] = asyncio.current_task()
            gate = self.controls[key] = asyncio.Event()
            gate.set()
            partial = self.store.directory / (key + '.part')
            try:
                for attempt in range(self.retries + 1):
                    try:
                        await gate.wait()
                        parallel = False
                        if spec.expected_size >= self.parallel_threshold and not partial.exists():
                            parallel = await self._multipart(key, spec, partial, gate)
                        if not parallel:
                            async with self.scheduler.slot(spec.uri):
                                await self._transfer(key, spec, partial, gate)
                        self.store.checkpoint(key, spec, 'VERIFYING', spec.expected_size)
                        if not await asyncio.to_thread(self.cache.verify, partial, spec):
                            partial.unlink(missing_ok=True)
                            raise IntegrityError('Downloaded size or digest does not match trusted metadata')
                        staged = self.cache.directory / (spec.sha256 + '.tmp')
                        def publish(staged=staged):
                            with open_private(staged) as output, partial.open('rb') as source:
                                shutil.copyfileobj(source, output, length=1024 * 1024)
                                output.flush()
                                os.fsync(output.fileno())
                            os.replace(staged, target)
                            partial.unlink()
                        await asyncio.to_thread(publish)
                        directory_fd = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY)
                        try:
                            os.fsync(directory_fd)
                        finally:
                            os.close(directory_fd)
                        self.store.checkpoint(key, spec, 'COMPLETE', spec.expected_size)
                        with self.store.db:
                            self.store.db.execute('INSERT OR REPLACE INTO cache_blobs(digest,size,path) VALUES(?,?,?)',
                                                  (spec.sha256, spec.expected_size, str(target)))
                        return str(target)
                    except IntegrityError:
                        raise
                    except Exception as exc:
                        if attempt == self.retries:
                            raise DownloadError(str(exc)) from exc
                        await asyncio.sleep(min(2 ** attempt, 4))
            except asyncio.CancelledError:
                self.store.checkpoint(key, spec, 'CANCELLED')
                partial.unlink(missing_ok=True)
                raise
            except Exception:
                saved = self.store.get(key)
                self.store.checkpoint(key, spec, 'FAILED',
                                      saved['bytes_written'] if saved else 0,
                                      saved['etag'] if saved else None)
                raise
            finally:
                lock_file.close()
                self.tasks.pop(key, None)
                self.controls.pop(key, None)
                self.bodies.pop(key, None)

    async def _multipart(self, key, spec, partial, gate):
        """Probe then acquire non-overlapping ranges; discard incomplete chunks on restart."""
        probe = self.store.directory / (key + '.probe')
        chunks = [self.store.directory / (key + f'.chunk{i}') for i in range(4)]
        self.store.checkpoint(key, spec, 'PROBING')
        try:
            async with self.scheduler.slot(spec.uri):
                validator = await self._range(spec, 0, 0, probe, gate, None, probe=True)
            if not validator:
                return False
            self.store.checkpoint(key, spec, 'DOWNLOADING', 0, validator)
            async def chunk(index):
                start = spec.expected_size * index // 4
                end = spec.expected_size * (index + 1) // 4 - 1
                async with self.scheduler.slot(spec.uri):
                    await self._range(spec, start, end, chunks[index], gate, validator)
            tasks = [asyncio.create_task(chunk(i)) for i in range(4)]
            try:
                await asyncio.gather(*tasks)
            finally:
                for task in tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
            def assemble():
                with open_private(partial) as output:
                    for path in chunks:
                        with path.open('rb') as source:
                            shutil.copyfileobj(source, output, length=1024 * 1024)
                    output.flush()
                    os.fsync(output.fileno())
            await asyncio.to_thread(assemble)
            return True
        finally:
            probe.unlink(missing_ok=True)
            for path in chunks:
                path.unlink(missing_ok=True)

    async def _range(self, spec, start, end, path, gate, validator, probe=False):
        await gate.wait()
        headers = {b'Accept-Encoding': [b'identity'],
                   b'Range': [f'bytes={start}-{end}'.encode()]}
        if validator:
            headers[b'If-Range'] = [validator.encode('latin1')]
        response = await asyncio.wait_for(_await(self.agent.request(
            b'GET', spec.uri.encode('ascii'), Headers(headers))), self.timeout)
        def header(name):
            values = response.headers.getRawHeaders(name, [])
            if len(values) > 1:
                return '<invalid duplicate header>'
            return values[0].decode('latin1') if values else None
        etag = header(b'ETag')
        valid = (response.code == 206 and
                 header(b'Content-Range') == f'bytes {start}-{end}/{spec.expected_size}' and
                 header(b'Content-Encoding') in (None, 'identity') and
                 header(b'Content-Length') in (None, str(end - start + 1)) and
                 bool(etag) and etag.startswith('"') and etag.endswith('"') and
                 (validator is None or validator == etag))
        if not valid:
            class Abort(Protocol):
                transport: Any
                def connectionMade(self):
                    self.transport.loseConnection()
            response.deliverBody(Abort())
            if probe:
                return None
            raise DownloadError('Multipart range or validator changed')
        with open_private(path) as file:
            body = _Body(file, end - start + 1, gate)
            self.bodies[path.name] = body
            response.deliverBody(body)
            try:
                count = await _consume(body, gate, self.timeout)
            finally:
                self.bodies.pop(path.name, None)
            if count != end - start + 1:
                raise DownloadError('Truncated range')
            file.flush()
            os.fsync(file.fileno())
        return etag

    async def _transfer(self, key, spec, partial, gate):
        row = self.store.get(key)
        offset, validator = 0, None
        if partial.is_symlink():
            raise ValueError('Symlink partial refused')
        if row and partial.exists() and row['etag'] and row['etag'].startswith('"') and row['etag'].endswith('"'):
            offset = partial.stat().st_size
            validator = row['etag']
            if offset >= spec.expected_size:
                offset, validator = 0, None
        headers = {b'Accept-Encoding': [b'identity']}
        if offset:
            assert validator is not None
            headers[b'Range'] = [f'bytes={offset}-'.encode()]
            headers[b'If-Range'] = [validator.encode('latin1')]
        response = await asyncio.wait_for(_await(self.agent.request(
            b'GET', spec.uri.encode('ascii'), Headers(headers))), self.timeout)
        def header(name):
            values = response.headers.getRawHeaders(name, [])
            if len(values) > 1:
                return '<invalid duplicate header>'
            return values[0].decode('latin1') if values else None
        etag = header(b'ETag')
        encoding = header(b'Content-Encoding')
        valid = response.code == 200 or (offset and response.code == 206)
        if response.code == 206:
            expected = f'bytes {offset}-{spec.expected_size - 1}/{spec.expected_size}'
            valid = valid and header(b'Content-Range') == expected and etag == validator
        if encoding not in (None, 'identity'):
            valid = False
        if response.code == 200:
            offset = 0  # Server ignored range / source validator changed: restart safely.
        length = header(b'Content-Length')
        if length is not None and length != str(spec.expected_size - offset):
            valid = False
        if not valid:
            # Abort rejected responses without buffering attacker-controlled content.
            class Abort(Protocol):
                transport: Any
                def connectionMade(self):
                    self.transport.loseConnection()
            response.deliverBody(Abort())
            partial.unlink(missing_ok=True)
            raise DownloadError(f'Invalid HTTP response or range ({response.code})')
        with open_private(partial, append=bool(offset)) as file:
            self.store.checkpoint(key, spec, 'DOWNLOADING', offset, etag)
            body = self.bodies[key] = _Body(file, spec.expected_size - offset, gate)
            response.deliverBody(body)
            try:
                await _consume(body, gate, self.timeout)
            finally:
                file.flush()
                os.fsync(file.fileno())
                self.store.checkpoint(key, spec, 'DOWNLOADING', offset + body.count, etag)
                self.bodies.pop(key, None)

    async def pause(self, download_id):
        self.controls[download_id].clear()
        for key, body in self.bodies.items():
            if key.startswith(download_id):
                body.transport.pauseProducing()
        with self.store.db:
            self.store.db.execute("UPDATE downloads SET state='PAUSED' WHERE id=?", (download_id,))

    async def resume(self, download_id):
        self.controls[download_id].set()
        with self.store.db:
            self.store.db.execute("UPDATE downloads SET state='DOWNLOADING' WHERE id=?", (download_id,))
        for key, body in self.bodies.items():
            if key.startswith(download_id):
                body.transport.resumeProducing()

    async def cancel(self, download_id):
        self.tasks[download_id].cancel()

    async def close(self):
        await _await(self.pool.closeCachedConnections())
        self.store.close()
