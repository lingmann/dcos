from fabric.api import run
from flask import Flask, request, render_template, url_for, redirect
import logging as log
import os
import yaml
#import unicodedata

"""
Global Variables 
"""
userconfig = {}


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
    do_routes(app, options)
    # Define the Flask log level if we set it un CLI flags
    if options.log_level == 'debug':
        app.debug = True

    app.run()


def do_routes(app, options):
    """
    Organize all our routes into a single def so we can keep
    all our routes defined in one place.
    """
    version = '1.0'

    @app.route("/", methods=['GET'])
    def redirectslash():
        return redirect(url_for('mainpage'))

    @app.route("/installer/v{}/".format(version), methods=['POST', 'GET'])
    def mainpage():
        if request.method == 'POST':
            add_config(request)
            dump_config(options.config_path) 
            # Return a redirect to a route handler via the configuration requirements
            return redirect(url_for(get_redirect(options.config_path)))        

        return render_template('main.html', title='Flask Test')


def add_config(data):
    """
    Updates the global userconfig{} map with the latest data from 
    the web console.
    """
    log.debug("Adding user config from form POST")
    log.debug("Received raw data: %s", data.form)
    for key in data.form.keys():
        log.debug(key, data.form[key])
        # Reencode the unicode string to an ASCII string for compatability
        userconfig[key] = data.form[key].encode('ascii','ignore')


def dump_config(path):
    """
    Dumps our configuration to the config path specific in CLI flags. If the file 
    already exists, add configuration to it from the userconfig presented to us 
    in the web console. Otherwise, if the file does no exist, create it and write the
    config passed to us from the console.
    """
    if os.path.exists(path):
        log.debug("Configuration path exists, reading in and adding config %s", path)
        base_config = yaml.load(open(path, 'r')) 
        for bk, bv in base_config.iteritems():
            log.debug("Adding pre-written configuration from yaml file %s: %s", bk, bv)
            userconfig[bk] = bv

    with open(path, 'w') as f:
        f.write(yaml.dump(userconfig, default_flow_style=False, explicit_start=True))


def get_config(path):
    """
    Returns the config file as a dict.
    """
    if os.stat.exists(path):
        log.debug("Reading in config file from %s", path)
        return yaml.load(open(path, 'r'))
    else:
        log.error("The configuration path does not exist %s", path)
        os.exit(1)


def get_redirect(config_path):
    """
    Defines our redirect logic. In the case of the installer,
    we have several parameters that require other paramters in the tree. 
    This method ensures the user gets redirected to the proper URI based
    on their initial top-level input to the installer.
    """
    config = get_config(config_path)

    #return redirect(url_for('login'))
