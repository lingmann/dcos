import aiohttp
import asyncio

from dcos_installer.async_server import app
from webtest_aiohttp import TestApp


version = 1
client = TestApp(app)
client.expect_errors = False


def test_redirect_to_root(monkeypatch):
    monkeypatch.setattr(aiohttp.parsers.StreamWriter, 'set_tcp_cork', lambda s, v: True)
    monkeypatch.setattr(aiohttp.parsers.StreamWriter, 'set_tcp_nodelay', lambda s, v: True)
    route = '/api/v{}'.format(version)
    featured_methods = {
        'GET': [302, 'text/plain', '/'],
        'POST': [405, 'text/plain'],
        'PUT': [405, 'text/plain'],
        'DELETE': [405, 'text/plain'],
        'HEAD': [405, 'text/plain'],
        'TRACE': [405, 'text/plain'],
        'CONNECT': [405, 'text/plain'],
    }
    for method, expected in featured_methods.items():
        res = client.request(route, method=method, expect_errors=True)
        assert res.status_code == expected[0], '{}: {}'.format(
            method,
            expected)
        assert res.content_type == expected[1], '{}: {}'.format(
            method,
            expected)
        if expected[0] == 'GET':
            assert res.location == expected[2], '{}: {}'.format(
                method,
                expected)


def test_configure(monkeypatch, mocker):
    monkeypatch.setattr(aiohttp.parsers.StreamWriter, 'set_tcp_cork', lambda s, v: True)
    monkeypatch.setattr(aiohttp.parsers.StreamWriter, 'set_tcp_nodelay', lambda s, v: True)
    route = '/api/v{}/configure'.format(version)
    featured_methods = {
        'GET': [200, 'application/json'],
        # Should return a 400 if validation has errors,
        # which this POST will return since the ssh_user
        # is an integer not a string.
        'POST': [400, 'application/json', '{"ssh_user": 1}'],
        'PUT': [405, 'text/plain'],
        'DELETE': [405, 'text/plain'],
        'HEAD': [405, 'text/plain'],
        'TRACE': [405, 'text/plain'],
        'CONNECT': [405, 'text/plain'],
    }
    mocked_get_config = mocker.patch('dcos_installer.backend.get_ui_config')
    mocked_create_config_from_post = mocker.patch('dcos_installer.backend.create_config_from_post')
    mocked_get_config.return_value = {"test": "config"}
    mocked_create_config_from_post.return_value = (True, None)

    for method, expected in featured_methods.items():
        if method == 'POST':
            res = client.request(route, method=method, body=bytes(expected[2].encode('utf-8')), expect_errors=True)
        else:
            res = client.request(route, method=method, expect_errors=True)
        assert res.status_code == expected[0], '{}: {}'.format(
            method,
            expected)
        assert res.content_type == expected[1], '{}: {}'.format(
            method,
            expected)
        if expected[0] == 200:
            assert res.json == {'test': 'config'}


def test_configure_status(monkeypatch, mocker):
    monkeypatch.setattr(aiohttp.parsers.StreamWriter, 'set_tcp_cork', lambda s, v: True)
    monkeypatch.setattr(aiohttp.parsers.StreamWriter, 'set_tcp_nodelay', lambda s, v: True)
    route = '/api/v{}/configure/status'.format(version)
    featured_methods = {
        # Defaults shouldn't pass validation, expect 400
        'GET': [400, 'application/json'],
        'POST': [405, 'text/plain'],
        'PUT': [405, 'text/plain'],
        'DELETE': [405, 'text/plain'],
        'HEAD': [405, 'text/plain'],
        'TRACE': [405, 'text/plain'],
        'CONNECT': [405, 'text/plain'],
    }
    mocked_return_configure_status = mocker.patch('dcos_installer.backend.return_configure_status')
    mocked_return_configure_status.return_value = {'errors': ['err1']}

    for method, expected in featured_methods.items():
        res = client.request(route, method=method, expect_errors=True)
        assert res.status_code == expected[0], '{}: {}'.format(method, expected)
        assert res.content_type == expected[1], '{}: {}'.format(method, expected)


def test_success(monkeypatch, mocker):
    monkeypatch.setattr(aiohttp.parsers.StreamWriter, 'set_tcp_cork', lambda s, v: True)
    monkeypatch.setattr(aiohttp.parsers.StreamWriter, 'set_tcp_nodelay', lambda s, v: True)
    route = '/api/v{}/success'.format(version)
    featured_methods = {
        'GET': [200, 'application/json'],
        'POST': [405, 'text/plain'],
        'PUT': [405, 'text/plain'],
        'DELETE': [405, 'text/plain'],
        'HEAD': [405, 'text/plain'],
        'TRACE': [405, 'text/plain'],
        'CONNECT': [405, 'text/plain'],
    }
    mocked_success = mocker.patch('dcos_installer.backend.success')
    mocked_success.return_value = {}

    for method, expected in featured_methods.items():
        res = client.request(route, method=method, expect_errors=True)
        assert res.status_code == expected[0], '{}: {}'.format(
            method,
            expected)
        assert res.content_type == expected[1], '{}: {}'.format(
            method,
            expected)


def action_action_name(route):
    featured_methods = {
        'GET': [200, 'application/json'],
        'POST': [200, 'application/json'],
        'PUT': [405, 'text/plain'],
        'DELETE': [405, 'text/plain'],
        'HEAD': [405, 'text/plain'],
        'TRACE': [405, 'text/plain'],
        'CONNECT': [405, 'text/plain'],
    }

    for method, expected in featured_methods.items():
        res = client.request(route, method=method, expect_errors=True)
        assert res.status_code == expected[0], '{}: {}'.format(
            method,
            expected)
        assert res.content_type == expected[1], '{}: {}'.format(
            method,
            expected)


def action_side_effect_return_config(arg):
    if arg == 'deploy_master':
        return {
            "hosts": {
                "10.33.2.21:22": {
                    "host_status": "failed",
                    "commands": [
                        {
                            "date": "2016-01-22 21:10:41.316282",
                            "returncode": 255,
                            "cmd": [
                                'cmd1'
                            ],
                            "stderr": [
                                ""
                            ],
                            "stdout": [
                                ""
                            ],
                            "pid": 2259
                        }
                    ]
                }
            },
            "chain_name": "deploy_master",
            "total_hosts": 1,
            "hosts_failed": 1
        }
    elif arg == 'deploy_agent':
        return {
            "hosts": {
                "10.33.2.22:22": {
                    "host_status": "success",
                    "commands": [
                        {
                            "date": "2016-01-22 21:10:41.316282",
                            "returncode": 0,
                            "cmd": [
                                'cmd2'
                            ],
                            "stderr": [
                                ""
                            ],
                            "stdout": [
                                ""
                            ],
                            "pid": 2260
                        }
                    ]
                }
            },
            "chain_name": "deploy_agent",
            "total_hosts": 1,
            "hosts_success": 1
        }
    return {
        arg: {
            'mock_config': True
        }
    }


def test_action_preflight(monkeypatch, mocker):
    monkeypatch.setattr(aiohttp.parsers.StreamWriter, 'set_tcp_cork', lambda s, v: True)
    monkeypatch.setattr(aiohttp.parsers.StreamWriter, 'set_tcp_nodelay', lambda s, v: True)
    route = '/api/v{}/action/preflight'.format(version)

    mocked_read_json_state = mocker.patch('dcos_installer.async_server.read_json_state')

    mocked_get_config = mocker.patch('dcos_installer.backend.get_ui_config')
    mocked_get_config.return_value = {"test": "config"}

    mocked_run_preflight = mocker.patch('dcos_installer.action_lib.run_preflight')
    mocked_run_preflight.return_value = (i for i in range(10))

    mocked_read_json_state.side_effect = action_side_effect_return_config
    res = client.request(route, method='GET')
    assert res.json == {'preflight': {'mock_config': True}}

    mocked_read_json_state.side_effect = lambda x: {}
    res = client.request(route, method='GET')
    assert res.json == {}


def test_action_postflight(monkeypatch, mocker):
    monkeypatch.setattr(aiohttp.parsers.StreamWriter, 'set_tcp_cork', lambda s, v: True)
    monkeypatch.setattr(aiohttp.parsers.StreamWriter, 'set_tcp_nodelay', lambda s, v: True)
    route = '/api/v{}/action/postflight'.format(version)

    mocked_read_json_state = mocker.patch('dcos_installer.async_server.read_json_state')

    mocked_get_config = mocker.patch('dcos_installer.backend.get_config')
    mocked_get_config.return_value = {"test": "config"}

    mocked_run_postflight = mocker.patch('dcos_installer.action_lib.run_postflight')
    mocked_run_postflight.return_value = (i for i in range(10))

    mocked_read_json_state.side_effect = action_side_effect_return_config
    res = client.request(route, method='GET')
    assert res.json == {'postflight': {'mock_config': True}}

    mocked_read_json_state.side_effect = lambda x: {}
    res = client.request(route, method='GET')
    assert res.json == {}


def test_action_deploy(monkeypatch, mocker):
    monkeypatch.setattr(aiohttp.parsers.StreamWriter, 'set_tcp_cork', lambda s, v: True)
    monkeypatch.setattr(aiohttp.parsers.StreamWriter, 'set_tcp_nodelay', lambda s, v: True)
    route = '/api/v{}/action/deploy'.format(version)

    mocked_read_json_state = mocker.patch('dcos_installer.async_server.read_json_state')

    mocked_get_config = mocker.patch('dcos_installer.backend.get_config')
    mocked_get_config.return_value = {"test": "config"}

    mocked_install_dcos = mocker.patch('dcos_installer.action_lib.install_dcos')
    mocked_install_dcos.return_value = (i for i in range(10))

    mocked_read_json_state.side_effect = action_side_effect_return_config
    res = client.request(route, method='GET')
    assert res.json == {
        "hosts": {
            "10.33.2.21:22": {
                "host_status": "failed",
                "commands": [
                    {
                        "date": "2016-01-22 21:10:41.316282",
                        "returncode": 255,
                        "cmd": [
                            'cmd1'
                        ],
                        "stderr": [
                            ""
                        ],
                        "stdout": [
                            ""
                        ],
                        "pid": 2259
                    }
                ]
            },
            "10.33.2.22:22": {
                "host_status": "success",
                "commands": [
                    {
                        "date": "2016-01-22 21:10:41.316282",
                        "returncode": 0,
                        "cmd": [
                            'cmd2'
                        ],
                        "stderr": [
                            ""
                        ],
                        "stdout": [
                            ""
                        ],
                        "pid": 2260
                    }
                ]
                }
        },
        "chain_name": "deploy",
        "total_hosts": 2,
        "hosts_success": 1,
        "hosts_failed": 1,
        "total_masters": 1,
        "total_agents": 1
    }

    mocked_read_json_state.side_effect = lambda x: {}
    res = client.request(route, method='GET')
    assert res.json == {}


def test_action_current(monkeypatch):
    monkeypatch.setattr(aiohttp.parsers.StreamWriter, 'set_tcp_cork', lambda s, v: True)
    monkeypatch.setattr(aiohttp.parsers.StreamWriter, 'set_tcp_nodelay', lambda s, v: True)
    route = '/api/v{}/action/current'.format(version)
    featured_methods = {
        'GET': [200, 'application/json'],
        'POST': [405, 'text/plain'],
        'PUT': [405, 'text/plain'],
        'DELETE': [405, 'text/plain'],
        'HEAD': [405, 'text/plain'],
        'TRACE': [405, 'text/plain'],
        'CONNECT': [405, 'text/plain'],
    }
    for method, expected in featured_methods.items():
        res = client.request(route, method=method, expect_errors=True)
        assert res.status_code == expected[0], '{}: {}'.format(
            method,
            expected)
        assert res.content_type == expected[1], '{}: {}'.format(
            method,
            expected)


def test_configure_type(monkeypatch, mocker):
    monkeypatch.setattr(aiohttp.parsers.StreamWriter, 'set_tcp_cork', lambda s, v: True)
    monkeypatch.setattr(aiohttp.parsers.StreamWriter, 'set_tcp_nodelay', lambda s, v: True)
    route = '/api/v{}/configure/type'.format(version)
    featured_methods = {
        'GET': [200, 'application/json'],
        'POST': [405, 'text/plain'],
        'PUT': [405, 'text/plain'],
        'DELETE': [405, 'text/plain'],
        'HEAD': [405, 'text/plain'],
        'TRACE': [405, 'text/plain'],
        'CONNECT': [405, 'text/plain'],
    }

    mocked_determine_config_type = mocker.patch('dcos_installer.backend.determine_config_type')
    mocked_determine_config_type.return_value = {}

    for method, expected in featured_methods.items():
        res = client.request(route, method=method, expect_errors=True)
        assert res.status_code == expected[0], '{}: {}'.format(
            method,
            expected)
        assert res.content_type == expected[1], '{}: {}'.format(
            method,
            expected)


def test_action_deploy_xxx(monkeypatch, mocker):
    monkeypatch.setattr(aiohttp.parsers.StreamWriter, 'set_tcp_cork', lambda s, v: True)
    monkeypatch.setattr(aiohttp.parsers.StreamWriter, 'set_tcp_nodelay', lambda s, v: True)
    route = '/api/v{}/action/deploy'.format(version)

    mocked_read_json_state = mocker.patch('dcos_installer.async_server.read_json_state')

    mocked_get_config = mocker.patch('dcos_installer.backend.get_config')
    mocked_get_config.return_value = {"test": "config"}

    @asyncio.coroutine
    def mock_coroutine(*args, **kwargs):
        yield from asyncio.sleep(.1)

    mocked_install_dcos = mocker.patch('dcos_installer.action_lib.install_dcos')
    mocked_install_dcos.side_effect = mock_coroutine

    # Deploy should be already executed for action 'deploy'
    mocked_read_json_state.side_effect = action_side_effect_return_config
    res = client.request(route, method='POST')
    assert res.json == {'status': 'deploy was already executed, skipping'}

    # Test start deploy
    mocked_read_json_state.side_effect = lambda arg: False
    res = client.request(route, method='POST')
    assert res.json == {'status': 'deploy started'}

    # Test retry
    def mocked_json_state(arg):
        if arg == 'deploy':
            return False

        if arg == 'deploy_master':
            return {
                'hosts': {
                    'master:22': {
                        'host_status': 'failed'
                    }
                }
            }

        if arg == 'deploy_agent':
            return {
                'hosts': {
                    'agent:22': {
                        'host_status': 'failed'
                    }
                }
            }

    mocked_install_dcos = mocker.patch('dcos_installer.action_lib.install_dcos')
    mocked_install_dcos.side_effect = mock_coroutine

    mocked_read_json_state.side_effect = mocked_json_state
    res = client.post(route, params={'retry': 'true'}, content_type='application/x-www-form-urlencoded')
    assert res.json == {'status': 'retried', 'details': {'deploy_agent': ['agent:22'], 'deploy_master': ['master:22']}}

    assert mocked_install_dcos.call_count == 2

    mocked_install_dcos.assert_any_call({'test': 'config'}, try_remove_stale_dcos=True, role='master', retry='true',
                                        hosts=['master:22'], state_json_dir='/genconf/state')

    mocked_install_dcos.assert_any_call({'test': 'config'}, try_remove_stale_dcos=True, role='agent', retry='true',
                                        hosts=['agent:22'], state_json_dir='/genconf/state')


# def test_logs(monkeypatch):
#    monkeypatch.setattr(aiohttp.parsers.StreamWriter, 'set_tcp_cork', lambda s, v: True)
#    monkeypatch.setattr(aiohttp.parsers.StreamWriter, 'set_tcp_nodelay', lambda s, v: True)
#    route = '/api/v{}/logs'.format(version)

# def test_serve_assets(monkeypatch):
#    monkeypatch.setattr(aiohttp.parsers.StreamWriter, 'set_tcp_cork', lambda s, v: True)
#    monkeypatch.setattr(aiohttp.parsers.StreamWriter, 'set_tcp_nodelay', lambda s, v: True)
#    route = '/api/v{}/assets'.format(version)
#    featured_methods = {
#        'GET': [200],
#        'POST': [405, 'text/plain'],
#        'PUT': [405, 'text/plain'],
#        'DELETE': [405, 'text/plain'],
#        'HEAD': [405, 'text/plain'],
#        'TRACE': [405, 'text/plain'],
#        'CONNECT': [405, 'text/plain']
#    }
#    filetypes = {
#        '.js': 'application/javascript',
#        '.json': 'application/json',
#        '.txt': 'text/plain'
#    }
#    for method, expected in featured_methods.items():
#       res = client.request(route, method=method, expect_errors=True)
#       assert res.status_code == expected[0], '{}: {}'.format(method, expected)
