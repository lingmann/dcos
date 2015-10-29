from copy import deepcopy
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

    @app.route("/installer/v{}/configurator/clear".format(version), methods=['POST'])
    def clear():
        clean_config(options.config_path)
        return redirect(redirect_url())


    @app.route("/installer/v{}/".format(version), methods=['POST', 'GET'])
    def mainpage():
        if request.method == 'POST':
            add_config(request)
            dump_config(options.config_path)
            # Redirects to correct page 
            return redirect(redirect_url())

        return render_template('main.html')
    
    # Configurator routes
    @app.route("/installer/v{}/configurator/".format(version))
    def configurator():
        config_level, message = validate(options.config_path)
        return render_template(
            'configurator.html',
            config_level=config_level,
            ip_detect_level="success")


    @app.route("/installer/v{}/configurator/ip-detect/".format(version))
    def ip_detect():
        return render_template('ip_detect.html')
        

    @app.route("/installer/v{}/configurator/config".format(version))
    def config():
        level, message = validate(options.config_path)
        return render_template(
            'config.html', 
            isset=get_config(options.config_path),
            dependencies=get_dependencies(options.config_path),
            validate_level = level,
            validate_message = message)


def add_config(data):
    """
    Updates the global userconfig{} map with the latest data from 
    the web console.
    """
    log.debug("Adding user config from form POST")
    log.debug("Received raw data: %s", data.form)
    for key in data.form.keys():
        log.debug("%s: %s",key, data.form[key])
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
            log.debug("Adding configuration from yaml file %s: %s", bk, bv)
            # Overwrite the yaml config with the config from the console
            try:
                if not userconfig[bk]:
                    userconfig[bk] = bv
            
            except:
                log.error("Configuration doesn't work %s: %s", bk, bv)

        with open(path, 'w') as f:
            f.write(yaml.dump(userconfig, default_flow_style=False, explicit_start=True))
    
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


def clean_config(path):
    """
    Fuckitshiptit method that clears the configuration.
    """
    log.debug("Clearing config...")
    userconfig = {}
    with open(path, 'w') as f:
        f.write(yaml.dump(userconfig, default_flow_style=False, explicit_start=True))

def validate(path):
    config = get_config(path)
    if config != {}:
        dependencies = get_dependencies(path)
        log.debug("Validating configruation file %s...", path)
        for dk, dv in dependencies.iteritems():
            log.debug("Checking coniguration for %s", dk)
            for required_value in dv:
                log.debug("Ensuring dependency %s exists in config", required_value)
                try:
                    log.debug("Value: %s", config[required_value])
                    if not config[required_value]:
                        log.warning("Found unneccessary data in %s: %s", path, config[required_value])
                        return "danger", 'Configuation is not valid: {}'.format(required_value)

                except:
                    log.info("Configuration looks good!")
                    return "success", "Configuration looks good!"
    
    else:
        log.warning("Configuration file is empty")
        return "warning", "Configuration file appears empty."
   

def redirect_url(default='mainpage'):
    return request.args.get('next') or \
        request.referrer or \
        url_for(default)


def get_dependencies(config_path):
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
        },
        "base": {
            "cluster_name": "", 
            "dns_resolvers": "", 
            "num_masters": "",
            "master_discovery": "",
            "exhibitor_storage_backend": ""
        },
    }
    # The final return dict 
    return_deps = {}
    # Get the master discovery deps
    if config.get('master_discovery'):
        try: 
            return_deps['master_discovery'] = dep_tree['master_discovery'][config['master_discovery']] 
        
        except: 
            log.error("The specified configuration value is not valid, %s", config['master_discovery'])
    
    # Get exhibitor storage deps
    if config.get('exhibitor_storage_backend'):
        try:
            return_deps['exhibitor_storage_backend'] = dep_tree['exhibitor_storage_backend'][config['exhibitor_storage_backend']] 
        
        except: 
            log.error("The specified configuration value is not valid, %s", config['master_discovery'])

    return_deps['base'] = dep_tree['base']
    return return_deps
