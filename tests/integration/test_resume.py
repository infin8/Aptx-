import pytest
from test_ranges import run_scenario


@pytest.mark.parametrize('mode', ['normal', 'ignore', 'bad'])
def test_persisted_resume(tmp_path, mode):
    run_scenario(tmp_path, f'''
        global MODE
        MODE = {mode!r}
        key = manager.download_id(spec)
        partial = manager.store.directory/(key+'.part')
        partial.write_bytes(DATA[:100])
        manager.store.checkpoint(key, spec, 'PAUSED', 100, '"v1"')
        manager.store.close()
        from aptx.persistence import StateStore
        manager.store = StateStore(root/'state')
        if MODE == 'bad':
            try:
                await manager.download(spec)
            except DownloadError:
                pass
            else:
                raise AssertionError('Bad Content-Range accepted')
        else:
            path = await manager.download(spec)
            assert Path(path).read_bytes() == DATA
        assert requests == ['bytes=100-']
    ''')
