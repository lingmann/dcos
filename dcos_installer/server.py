import json
import logging

from flask import (
    Flask,
    redirect,
    url_for,
    request,
    render_template,
    Response)

from dcos_installer import (
    mock,
    backend)

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
            """
            Overwrite the data in config.yaml with the data in POST. Return
            the validation messages and config file. Concatonate the two
            together and return a giant JSON of config + messages.
            """
            new_config = request.json
            log.info('POST to configure: {}'.format(new_config))
            messages, config = mock.validate(new_config)
            concat = dict(config, **messages)
            resp = Response(json.dumps(concat))

            # if not len(messages['errors']) > 0:
            #    backend.configure(options)
            backend.configure(options)

            resp.headers['Content-Type'] = 'application/json'
            return resp

        elif request.method == 'GET':
            """
            Return the written configuration on disk. This route assumes the
            config.yaml is on disk, however, we're currently writing it into
            the mock.py file directly - we can update the validate to take the
            config file path, and read from that instead. It concats the two
            dictionaries together like POST does.
            """
            messages, config = mock.validate()
            concat = dict(config, **messages)
            resp = Response(json.dumps(concat))
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

    app.run(host='0.0.0.0')
