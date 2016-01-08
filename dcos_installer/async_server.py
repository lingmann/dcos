import asyncio
import logging

import pkg_resources
from dcos_installer import backend, mock

from aiohttp import web

log = logging.getLogger("aiohttp.web")

version = '1'

log.info("Starting DCOS Installer")


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
    log.info("/api/v{} -> redirecting -> /".format(version))
    return web.HTTPFound('/'.format(version))


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
        messages, _ = mock.validate(new_config)
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
        _, config = mock.validate()
        resp = web.json_response(config)

    resp.headers['Content-Type'] = 'application/json'
    return resp


# Configuration validation route handler
def configure_status(request):
    log.info("Request for configuration validation made.")
    messages, _ = mock.validate()
    resp = web.json_response({})
    if messages['errors'] and len(messages['errors']) > 0:
        resp = web.json_response(messages['errors'], status=400)

    return resp


# Success route handler
def success(request):
    return web.json_response(mock.mock_success())


# TODO action_ID implementation

# Define the aiohttp web application framework and setup
# the routes to be used in the API.
loop = asyncio.get_event_loop()
app = web.Application(loop=loop)

# Serve static files:
# app.router.add_static('/', pkg_resources.resource_filename(__name__, 'css/'))

# Static routes
app.router.add_route('GET', '/', root)
app.router.add_route('GET', '/api/v{}'.format(version), redirect_to_root)
app.router.add_route('GET', '/api/v{}/configure'.format(version), configure)
app.router.add_route('POST', '/api/v{}/configure'.format(version), configure)
app.router.add_route('GET', '/api/v{}/configure/status'.format(version), configure_status)
app.router.add_route('GET', '/api/v{}/success'.format(version), success)


def start(port):
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
