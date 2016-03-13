import os

from dcos_installer import async_server


def test_merge_json():
    r = {}
    json_data1 = {
        'string': 'value',
        'name': 'deploy_master',
        'abc': {
            'foo': 'bar'
        },
        'counter': 5
    }
    async_server._merge_json(r, json_data1, 'deploy_master')
    assert r == {'name': 'deploy', 'string': 'value', 'counter': 5, 'abc': {'foo': 'bar'}}
    json_data2 = {
        'string': 'value',
        'name': 'deploy_agent',
        'counter': 1,
        'abc': {
            'key': 'value'
        }
    }
    async_server._merge_json(r, json_data2, 'deploy_agent')
    assert r == {
        'abc': {
            'foo': 'bar',
            'key': 'value',
            },
        'counter': 6,
        'name': 'deploy',
        'string': 'value'
    }


def test_unlink_state_file(monkeypatch):
    monkeypatch.setattr(os.path, 'isfile', lambda x: True)

    def mocked_unlink(path):
        assert path == '/genconf/state/preflight.json'

    monkeypatch.setattr(os, 'unlink', mocked_unlink)
    async_server.unlink_state_file('preflight')
