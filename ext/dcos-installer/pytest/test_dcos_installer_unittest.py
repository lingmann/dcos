import unittest
from unittest import mock
from dcos_installer import async_server


class TestDcosInstaller(unittest.TestCase):
    def test_merge_json(self):
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

    @mock.patch('os.path.isfile')
    @mock.patch('os.unlink')
    def test_unlink_state_file(self, mocked_unlink, mocked_isfile):
        mocked_isfile.return_value = True
        async_server.unlink_state_file('preflight')
        mocked_unlink.assert_called_with('/genconf/state/preflight.json')
