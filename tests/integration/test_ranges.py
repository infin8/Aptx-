"""Subprocess isolation ensures each test owns its asyncio Twisted reactor."""
import subprocess
import sys
import textwrap


def run_scenario(tmp_path, scenario):
    source = '''
import asyncio, hashlib, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from twisted.internet import asyncioreactor
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
asyncioreactor.install(loop)
from twisted.internet import reactor
from aptx.downloader import DownloadManager, DownloadSpec, IntegrityError, DownloadError
DATA = b'payload' * 10000
requests = []
MODE = 'normal'
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def do_GET(self):
        request_range = self.headers.get('Range')
        requests.append(request_range)
        start = int(request_range.split('=')[1].split('-')[0]) if request_range else 0
        ranged = bool(request_range) and MODE != 'ignore'
        if not ranged: start = 0
        end = int(request_range.split('-')[1]) if ranged and request_range.split('-')[1] else len(DATA)-1
        data = DATA[start:end+1]
        self.send_response(206 if ranged else 200)
        if MODE != 'novalidator': self.send_header('ETag', '"v1"')
        self.send_header('Content-Length', str(len(data)))
        if ranged:
            self.send_header('Content-Range', f'bytes {start if MODE != "bad" else start + 1}-{end}/{len(DATA)}')
        self.end_headers()
        if MODE == 'slow':
            for offset in range(0, len(data), 1024):
                self.wfile.write(data[offset:offset+1024])
                self.wfile.flush()
                time.sleep(0.003)
        else:
            self.wfile.write(data)
server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
root = Path(ROOT)
spec = DownloadSpec('pkg','1',f'http://127.0.0.1:{server.server_port}/pkg',len(DATA),hashlib.sha256(DATA).hexdigest())
async def main():
    manager = DownloadManager(root/'state', root/'cache', retries=0)
    try:
SCENARIO
    finally:
        await manager.close()
        server.shutdown()
async def entry():
    try:
        await main()
    finally:
        reactor.stop()
reactor.callWhenRunning(lambda: loop.create_task(entry()))
reactor.run()
'''
    # Tasks must propagate failures to the subprocess exit status.
    source = source.replace('async def entry():', 'failure = []\nasync def entry():').replace(
        '        await main()\n    finally:', '        await main()\n    except BaseException as exc:\n        failure.append(exc)\n    finally:')
    source += '\nif failure: raise failure[0]\n'
    source = source.replace('ROOT', repr(str(tmp_path))).replace('SCENARIO', textwrap.indent(textwrap.dedent(scenario).strip(), '        '))
    result = subprocess.run([sys.executable, '-c', source], capture_output=True, text=True, timeout=25, check=False)
    assert result.returncode == 0, result.stderr[-6000:]


def test_download_and_verified_cache(tmp_path):
    run_scenario(tmp_path, '''
        path = await manager.download(spec)
        assert Path(path).read_bytes() == DATA
        await manager.download(spec)
        assert len(requests) == 1
        Path(path).write_bytes(b'corrupt')
        await manager.download(spec)
        assert len(requests) == 2
    ''')


def test_integrity_failure(tmp_path):
    run_scenario(tmp_path, '''
        from dataclasses import replace
        try:
            await manager.download(replace(spec, sha256='0' * 64))
        except IntegrityError:
            pass
        else:
            raise AssertionError('Digest mismatch accepted')
        assert not (root/'cache'/('0'*64)).exists()
    ''')


def test_multipart(tmp_path):
    run_scenario(tmp_path, """
        global DATA
        DATA = b'payload' * 200000
        from dataclasses import replace
        large = replace(spec, expected_size=len(DATA), sha256=hashlib.sha256(DATA).hexdigest())
        path = await manager.download(large)
        assert Path(path).read_bytes() == DATA
        assert len(requests) == 5
        assert requests[0] == 'bytes=0-0'
    """)


def test_multipart_without_validator_falls_back(tmp_path):
    run_scenario(tmp_path, """
        global DATA, MODE
        MODE = 'novalidator'
        DATA = b'payload' * 200000
        from dataclasses import replace
        large = replace(spec, expected_size=len(DATA), sha256=hashlib.sha256(DATA).hexdigest())
        path = await manager.download(large)
        assert Path(path).read_bytes() == DATA
        assert requests == ['bytes=0-0', None]
    """)


def test_wrong_sha512_rejected(tmp_path):
    run_scenario(tmp_path, """
        from dataclasses import replace
        try:
            await manager.download(replace(spec, sha512='0' * 128))
        except IntegrityError:
            pass
        else:
            raise AssertionError('SHA512 mismatch accepted')
    """)


def test_pause_resume_and_cancel(tmp_path):
    run_scenario(tmp_path, """
        global MODE
        MODE = 'slow'
        task = asyncio.create_task(manager.download(spec))
        key = manager.download_id(spec)
        while not manager.bodies:
            await asyncio.sleep(0.005)
        await manager.pause(key)
        assert manager.store.get(key)['state'] == 'PAUSED'
        count = manager.bodies[key].count
        await asyncio.sleep(0.08)
        assert manager.bodies[key].count == count
        await manager.resume(key)
        path = await task
        assert Path(path).read_bytes() == DATA
        Path(path).unlink()
        task = asyncio.create_task(manager.download(spec))
        while not manager.bodies:
            await asyncio.sleep(0.005)
        await manager.cancel(key)
        try:
            await task
        except asyncio.CancelledError:
            pass
        else:
            raise AssertionError('Task was not cancelled')
        assert manager.store.get(key)['state'] == 'CANCELLED'
        assert not (manager.store.directory/(key+'.part')).exists()
    """)
