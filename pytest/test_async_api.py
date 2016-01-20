import aiohttp

from dcos_installer.async_server import app
from webtest_aiohttp import TestApp


version = 1
client = TestApp(app)
client.expect_errors = False


def test_root_route(monkeypatch):
    monkeypatch.setattr(aiohttp.parsers.StreamWriter, 'set_tcp_cork', lambda s, v: True)
    monkeypatch.setattr(aiohttp.parsers.StreamWriter, 'set_tcp_nodelay', lambda s, v: True)
    route = '/'
    featured_methods = {
        'GET': [200, 'text/html'],
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


def test_configure(monkeypatch):
    monkeypatch.setattr(aiohttp.parsers.StreamWriter, 'set_tcp_cork', lambda s, v: True)
    monkeypatch.setattr(aiohttp.parsers.StreamWriter, 'set_tcp_nodelay', lambda s, v: True)
    route = '/api/v{}/configure'.format(version)
    featured_methods = {
        'GET': [200, 'application/json'],
        # Should return a 400 if validation has errors,
        # which this POST will return since the ssh_user
        # is an integer not a string.
        'POST': [
            400,
            'application/json',
            '{"ssh_user": 1}'],
        'PUT': [405, 'text/plain'],
        'DELETE': [405, 'text/plain'],
        'HEAD': [405, 'text/plain'],
        'TRACE': [405, 'text/plain'],
        'CONNECT': [405, 'text/plain'],
    }
    for method, expected in featured_methods.items():
        if method == 'POST':
            res = client.request(
                route,
                method=method,
                body=bytes(expected[2].encode('utf-8')),
                expect_errors=True)
        else:
            res = client.request(route, method=method, expect_errors=True)
        assert res.status_code == expected[0], '{}: {}'.format(
            method,
            expected)
        assert res.content_type == expected[1], '{}: {}'.format(
            method,
            expected)


def test_configure_status(monkeypatch):
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
    for method, expected in featured_methods.items():
        res = client.request(route, method=method, expect_errors=True)
        assert res.status_code == expected[0], '{}: {}'.format(
            method,
            expected)
        assert res.content_type == expected[1], '{}: {}'.format(
            method,
            expected)


def test_success(monkeypatch):
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
    for method, expected in featured_methods.items():
        res = client.request(route, method=method, expect_errors=True)
        assert res.status_code == expected[0], '{}: {}'.format(
            method,
            expected)
        assert res.content_type == expected[1], '{}: {}'.format(
            method,
            expected)


def test_action_deploy(monkeypatch):
    monkeypatch.setattr(aiohttp.parsers.StreamWriter, 'set_tcp_cork', lambda s, v: True)
    monkeypatch.setattr(aiohttp.parsers.StreamWriter, 'set_tcp_nodelay', lambda s, v: True)
    route = '/api/v{}/action/deploy'.format(version)
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


def test_action_preflight(monkeypatch):
    monkeypatch.setattr(aiohttp.parsers.StreamWriter, 'set_tcp_cork', lambda s, v: True)
    monkeypatch.setattr(aiohttp.parsers.StreamWriter, 'set_tcp_nodelay', lambda s, v: True)
    route = '/api/v{}/action/preflight'.format(version)
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


def test_action_postflight(monkeypatch):
    monkeypatch.setattr(aiohttp.parsers.StreamWriter, 'set_tcp_cork', lambda s, v: True)
    monkeypatch.setattr(aiohttp.parsers.StreamWriter, 'set_tcp_nodelay', lambda s, v: True)
    route = '/api/v{}/action/postflight'.format(version)
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


def test_configure_type(monkeypatch):
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
    for method, expected in featured_methods.items():
        res = client.request(route, method=method, expect_errors=True)
        assert res.status_code == expected[0], '{}: {}'.format(
            method,
            expected)
        assert res.content_type == expected[1], '{}: {}'.format(
            method,
            expected)


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
#        'CONNECT': [405, 'text/plain'],
#    }
#    filetypes = {
#        '.js': 'application/javascript',
#        '.json': 'application/json',
#        '.txt': 'text/plain'
#    }
#    for method, expected in featured_methods.items():
#        res = client.request(route, method=method, expect_errors=True)
#        assert res.status_code == expected[0], '{}: {}'.format(
#            method,
#            expected)
