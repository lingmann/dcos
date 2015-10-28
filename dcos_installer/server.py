from fabric.api import run
from flask import Flask
from flask import request
from flask import render_template
import logging as log
import yaml

def run(options):
    """
    Define some routes and execute the Flask server. Currently
    pinning the routes with v1.0 to allow for seamless upgrades
    in the future.
    """
    log.info("Executing Flask server...")
    # Define a new Flask object
    app = Flask(__name__)
    # Create our app URIs
    do_routes(app,options)
    # Define the Flask log level if we set it un CLI flags
    if options.log_level == 'debug':
        app.debug = True

    app.run()


def do_routes(app,options):
    """
    Organize all our routes into a single def so we can keep
    all our routes defined in one place.
    """
    version = '1.0'
    @app.route("/installer/v{}/".format(version), methods=['POST', 'GET'])
    def mainpage():
        if request.method == 'POST':
            log.debug("Dumping configruation from form...")
            dump_configuration(options.config_path,request.form)
                        
        return render_template('main.html', title='Flask Test')

def dump_configuration(path, data):
    """
    Dumps our configuration to the config path specific in CLI flags.
    """
    log.info("Dumping configuration from form to ", path)
    with open(path, 'w') as f:
        f.write(yaml.dump(data, default_flow_style=True))


def do_redirect(app):
    """
    Defines our redirect logic. In the case of the installer,
    we have several parameters that require other paramters in the tree. 
    This method ensures the user gets redirected to the proper URI based
    on their initial top-level input to the installer.
    """
    return "this"
       # abort(404)
    #return redirect(url_for('login'))
