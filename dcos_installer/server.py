import json
import logging

from flask import (
    Flask,
    redirect,
    url_for,
    request,
    render_template,
    Response)

from installer import mock

log = logging.getLogger(__name__)

"""
Define some routes and execute the Flask server. Currently
pinning the routes with v1.0 to allow for seamless upgrades
in the future.
"""
log.info("Starting UI for DCOS installer...")
app = Flask(__name__)
version = '1'
action_names = ['deploy', 'preflight', 'postflight']


def start(options):
    @app.route('/', methods=['GET'])
    def root():
        log.info("Root page requested")
        return redirect(url_for('main'))


    @app.route('/api/v{}'.format(version), methods=['GET'])
    def main():
        log.info("Main page requested")
        return render_template('index.html')


    @app.route('/api/v{}/configure'.format(version), methods=['GET', 'POST'])
    def configure():
        if request.method == 'POST':
            new_config = request.json
            log.info('POST to configure: {}'.format(new_config))
            _, config = mock.validate(new_config)
            resp = Response(json.dumps(config))
            resp.headers['Content-Type'] = 'application/json'
            return resp

        elif request.method == 'GET':
            _, config = mock.validate()
            resp = Response(json.dumps(config))
            resp.headers['Content-Type'] = 'application/json'
            return resp


    @app.route('/api/v{}/<action_name>'.format(version), methods=['GET', 'POST'])
    def do_action_name(action_name):
        if action_name in action_names:
            if request.method == 'GET':
                log.info('GET {}'.format(action_name))
                # Do nothing
            elif request.method == 'POST':
                log.info('POST {}'.format(action_name))
                # Execute deploy wrapper

            return json.dumps(mock.mock_action_state)

            # TODO(malnick)
            # Flask handles returning the 405 for method not allowed for us,
            # unsure if we want to implement our own internal exception when
            # a method not allowed is used?

        else:
            log.error('Action not supported. Supported actions: {}'.format(action_names))
            return render_template('404.html'), 404


    @app.route('/api/v{}/success'.format(version), methods=['GET'])
    def success():
        return json.dumps(mock.mock_success())


    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('404.html'), 404

    app.run()
