import asyncio
import json
import logging
import os

import pkg_resources
from aiohttp import web

from dcos_installer import action_lib, backend

log = logging.getLogger()

VERSION = '1'

state_dir = '/genconf/state'

# Define the aiohttp web application framework and setup
# the routes to be used in the API.
loop = asyncio.get_event_loop()
app = web.Application(loop=loop)
app['current_action'] = ''

action_map = {
    'preflight': action_lib.run_preflight,
    'deploy_master': lambda *args, **kwargs: action_lib.install_dcos(*args, role='master', **kwargs),
    'deploy_agent': lambda *args, **kwargs: action_lib.install_dcos(*args, role='agent', **kwargs),
    'postflight': action_lib.run_postflight,
    'deploy': ['deploy_master', 'deploy_agent']
}

remove_on_done = ['preflight', 'postflight']


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
        log.info('POST to configure: {}'.format(new_config))
        validation_err, messages = backend.create_config_from_post(new_config)

        resp = web.json_response({}, status=200)
        if validation_err:
            resp = web.json_response(messages, status=400)

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
    messages = backend.return_configure_status()
    resp = web.json_response({}, status=200)
    if 'errors' in messages and len(messages['errors']) > 0:
        resp = web.json_response(messages['errors'], status=400)

    else:
        backend.do_configure()

    return resp


def configure_type(request):
    log.info("Request for configuration type made.")
    return web.json_response(backend.determine_config_type())


# Success route handler
def success(request):
    return web.json_response(backend.success())


def _merge_json(result, data_json, original_action):
    total_role = 'total_{}s'.format(original_action.split('_').pop())
    if total_role not in result:
        if 'total_hosts' in data_json:
            result[total_role] = data_json['total_hosts']

    for key, value in data_json.items():
        # Increment ints
        if isinstance(value, int):
            value = result.get(key, 0) + value
        elif isinstance(value, dict):
            if key in result:
                result[key].update(value)
                continue
            else:
                result[key] = value
        elif isinstance(value, str):
            if value.startswith('deploy') and not value.endswith('deploy'):
                value = 'deploy'

        result.update({key: value})


def unlink_state_file(action_name):
    json_status_file = state_dir + '/{}.json'.format(action_name)
    if os.path.isfile(json_status_file):
        log.debug('removing {}'.format(json_status_file))
        os.unlink(json_status_file)
        return True
    log.debug('cannot remove {}, file not found'.format(json_status_file))
    return False


def read_json_state(action_name):
    json_status_file = state_dir + '/{}.json'.format(action_name)
    if not os.path.isfile(json_status_file):
        return False

    with open(json_status_file) as fh:
        return json.load(fh)


def action_action_name(request):
    action_name = request.match_info['action_name']
    # get_action_status(action_name)
    # if action_status == not_running
    #     cleanup_action_jsons(action_name)
    # ...execute action again.
    #
    # Update the global action
    json_state = read_json_state(action_name)
    app['current_action'] = action_name

    if request.method == 'GET':
        log.info('GET {}'.format(action_name))

        action_key = action_map.get(action_name)
        if isinstance(action_key, list):
            # Deploy action consits of 2 json states: deploy_agent.json and deploy_master.json
            result = {}
            for action in action_key:
                json_state = read_json_state(action)
                if not json_state:
                    return web.json_response({})
                _merge_json(result, json_state, action)
            return web.Response(body=json.dumps(result, sort_keys=True, indent=4).encode('utf-8'),
                                content_type='application/json')
        if json_state:
            return web.Response(body=json.dumps(json_state, sort_keys=True, indent=4).encode('utf-8'),
                                content_type='application/json')

        return web.json_response({})

    elif request.method == 'POST':
        log.info('POST {}'.format(action_name))
        # If the action name is preflight, attempt to run configuration
        # generation. If genconf fails, present the UI with a usable error
        # for the end-user
        if action_name == 'preflight':
            try:
                backend.do_configure()
            except:
                genconf_failure = {
                    "errors": "Configuration generation failed, please see command line for details"
                }
                return web.json_response(genconf_failure, status=400)

        params = yield from request.post()
        if json_state:
            if action_name not in remove_on_done:
                return web.json_response({'status': '{} was already executed, skipping'.format(action_name)})
            running = False

            for host, attributes in json_state['hosts'].items():
                if attributes['host_status'].lower() == 'running':
                    running = True

            log.debug('is action running: {}'.format(running))
            if running:
                return web.json_response({'status': '{} is running, skipping'.format(action_name)})
            else:
                unlink_state_file(action_name)

        action = action_map.get(action_name)
        if not action:
            return web.json_response({'error': 'action {} not implemented'.format(action_name)})

        if isinstance(action, list):
            deploy_executed = False
            for new_action_str in action:
                new_json_state = read_json_state(new_action_str)
                if new_json_state:
                    deploy_executed = True

            if deploy_executed:
                return web.json_response({'status': 'deploy was already executed, skipping'})
            else:
                for new_action_str in action:
                    new_action = action_map.get(new_action_str)
                    log.info('Executing {}'.format(new_action_str))
                    yield from asyncio.async(new_action(backend.get_config(), state_json_dir=state_dir, **params))
        else:
            yield from asyncio.async(action(backend.get_config(), state_json_dir=state_dir, **params))
        return web.json_response({'status': '{} started'.format(action_name)})


def action_current(request):
    action = app['current_action']
    return_json = {'current_action': action}
    return web.json_response(return_json)


# Serve static files:
app.router.add_static('/assets', pkg_resources.resource_filename(__name__, 'templates/assets/'))

# Static routes
app.router.add_route('GET', '/', root)
app.router.add_route('GET', '/api/v{}'.format(VERSION), redirect_to_root)
app.router.add_route('GET', '/api/v{}/configure'.format(VERSION), configure)
app.router.add_route('POST', '/api/v{}/configure'.format(VERSION), configure)
app.router.add_route('GET', '/api/v{}/configure/status'.format(VERSION), configure_status)
app.router.add_route('GET', '/api/v{}/configure/type'.format(VERSION), configure_type)
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
    if not os.path.isdir(state_dir):
        os.mkdir(state_dir)

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        srv.close()
        loop.run_until_complete(handler.finish_connections(1.0))
        loop.run_until_complete(app.finish())
    loop.close()
