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


    @app.route("/installer/v{}/configurator".format(version))
    def master_discovery_static_route():
        return render_template(
            'config.html', 
            isset=get_config(options.config_path),
            dependencies={})


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
            if not userconfig[bk]:
                userconfig[bk] = bv
    
    if not os.path.exists(path):
        with open(path, 'w') as f:
            f.write(yaml.dump(userconfig, default_flow_style=False, explicit_start=True))


def get_config(path):
    """
    Returns the config file as a dict.
    """
    if os.path.exists(path):
        log.debug("Reading in config file from %s", path)
        return yaml.load(open(path, 'r'))
    else:
        log.error("The configuration path does not exist %s", path)
        return {}

def get_redirect(config_path):
    """
    Defines our redirect logic. In the case of the installer,
    we have several parameters that require other paramters in the tree. 
    This method ensures the user gets redirected to the proper URI based
    on their initial top-level input to the installer.
    """
    config = get_config(config_path)

    dep_tree = {
        "master_discovery": {
            "static":  ["master_list"],
            "keepalived": ["keepalived_router_id", "keepalived_interface", "keepalived_pass", "keepalived_virtual_ipaddress"],
            "cloud_dynamic": ["num_masters"],
        },
        "exhibitor_storage_backend": {
            "zookeeper": ["exhibitor_zk_hosts", "exhibitor_zk_path"],
            "shared_fs": ["exhibitor_fs_config_path"],
            "aws_s3": ["aws_access_key_id", "aws_secret_access_key", "aws_region", "s3_bucket", "s3_prefix"],
        }
    }
    
    if config.get('master_discovery'):
        for value in dep_tree['master_discovery'][config['master_discovery']]:
            log.debug("Checking for dependency %s", value)
            if config.get('value'):
                log.debug("Dependency found, %s", value)
                continue
            else:
                log.debug("Dependency not found, %s", value)
                return 'master_discovery_{}_route'.format(config['master_discovery']) 

    else:
        log.error('The master_discovery key does not exist, please restart the installer or add it manually.')
        return("mainpage")
    #return redirect(url_for('login'))
