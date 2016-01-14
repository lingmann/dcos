import asyncio
import logging

import pkg_resources
from aiohttp import web

from aiohttp_session import get_session, session_middleware, SimpleCookieStorage
from dcos_installer import backend, mock

log = logging.getLogger()

VERSION = '1'


# class CurrentAction():

# Aiohttp route handlers. These methods are for the
# aiohttp routes. Some are asyncio.coroutines and
# some are not.
def root(request):
    log.info("Root page requested.")
    index_path = pkg_resources.resource_filename(__name__, 'templates/index.html')
    index_file = open(index_path)
    log.info("Serving %s", index_path)
    resp = web.Response(body=index_file.read().encode('utf-8'))
    resp.headers['content-type'] = 'text/html'
    return resp


# Redirect to root method handler
def redirect_to_root(request):
    log.info("/api/v{} -> redirecting -> /".format(VERSION))
    return web.HTTPFound('/'.format(VERSION))


# Configure route method handler
def configure(request):
    if request.method == 'POST':
        """
        Overwrite the data in config.yaml with the data in POST. Return
        the validation messages and config file. Concatonate the two
        together and return a giant JSON of config + messages.
        """
        new_config = yield from request.json()
        log.info("Received: %s", new_config)
        log.info('POST to configure: {}'.format(new_config))
        if 'ssh_key' in new_config:
            backend.write_ssh_key(new_config['ssh_key'])
        messages = backend.create_config_from_post(new_config)
        resp = web.json_response({})
        if messages['errors'] and len(messages['errors']) > 0:
            resp = web.json_response(messages['errors'], status=400)

        else:
            # Execute genconf
            backend.configure()
            resp = web.json_response({}, status=200)

        return resp
        # TODO (malnick/cmalony) implement the proper call to the gen
        # library to write, validate and generate genconf configuration.
        # backend.configure()

    elif request.method == 'GET':
        """
        Return the written configuration on disk.
        """
        config = backend.get_config()
        resp = web.json_response(config)

    resp.headers['Content-Type'] = 'application/json'
    return resp


# Configuration validation route handler
def configure_status(request):
    log.info("Request for configuration validation made.")
    # TODO(malnick) Update this to point to backend.py with call to Gen validation
    messages = mock.validate()
    resp = web.json_response({})
    if messages['errors'] and len(messages['errors']) > 0:
        resp = web.json_response(messages['errors'], status=400)

    return resp


# Success route handler
def success(request):
    return web.json_response(backend.success())


def action_action_name(request):
    action_name = request.match_info['action_name']
    # Create a new globally accessibly session and set the
    # current_action name to action_name. We return this in
    # the route for action_name/current.
    # session = yield from get_session(request)
    # session['current_action'] = action_name
    if request.method == 'GET':
        log.info('GET {}'.format(action_name))
        return web.json_response(action_name)

    elif request.method == 'POST':
        log.info('POST {}'.format(action_name))
        return web.json_response(action_name)


def action_current(request):
     #current_action = current_action  # yield from get_session(request)
    # current_action = session['current_action']
    return web.json_response(current_action)

# Define the aiohttp web application framework and setup
# the routes to be used in the API.
loop = asyncio.get_event_loop()
app = web.Application(
    loop=loop,
    middlewares=[session_middleware(SimpleCookieStorage())])

# Serve static files:
# app.router.add_static('/', pkg_resources.resource_filename(__name__, 'css/'))

# Static routes
app.router.add_route('GET', '/', root)
app.router.add_route('GET', '/api/v{}'.format(VERSION), redirect_to_root)
app.router.add_route('GET', '/api/v{}/configure'.format(VERSION), configure)
app.router.add_route('POST', '/api/v{}/configure'.format(VERSION), configure)
app.router.add_route('GET', '/api/v{}/configure/status'.format(VERSION), configure_status)
app.router.add_route('GET', '/api/v{}/success'.format(VERSION), success)
# TODO(malnick) The regex handling in the variable routes blows up if we insert another variable to be
# filled in by .format. Had to hardcode the VERSION into the URL for now. Fix suggestions please!
app.router.add_route('GET', '/api/v1/action/{action_name:preflight|postflight|deploy}', action_action_name)
app.router.add_route('POST', '/api/v1/action/{action_name:preflight|postflight|deploy}', action_action_name)
app.router.add_route('GET', '/api/v{}/action/current'.format(VERSION), action_current)


def start(port=9000):
    log.debug('DCOS Installer V{}'.format(VERSION))
    handler = app.make_handler()
    f = loop.create_server(
        handler,
        '0.0.0.0',
        port)
    srv = loop.run_until_complete(f)
    log.info('Starting server {}'.format(srv.sockets[0].getsockname()))

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        srv.close()
        loop.run_until_complete(handler.finish_connections(1.0))
        loop.run_until_complete(app.finish())
    loop.close()
