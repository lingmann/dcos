from flask import Flask, request, render_template, url_for, redirect, Response
import os
import yaml
from glob import glob

# Logging
from dcos_installer.log import DCOSLog
log = DCOSLog(__name__).log

# From dcos-image
#import gen
#from providers import bash

# Helper submodules
from dcos_installer.config import DCOSConfig
from dcos_installer.validate import ext_helpers, DCOSValidateConfig

"""
Global Variables 
"""
# Sane user config defaults
userconfig = DCOSConfig({'install_type': 'onprem'})

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

    app.run(port=options.port)


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


    @app.route("/installer/v{}/".format(version), methods=['GET'])
    def mainpage():
        """
        The mainpage handler
        """
        return render_template('main.html')
    

    # Configurator routes
    @app.route("/installer/v{}/configurator/".format(version), methods=['GET', 'POST'])
    def configurator():
        """
        The top level configurator route. This route exposes the two options to go
        to the configurator wizard or to upload the ip script. This will probably
        be changed in the future.
        """
        if request.method == 'POST':
            # Save or upload configuration posted
            if 'ssh_key' in request.files:
                log.info("Upload SSH key")
                save_file(
                    request.files['ssh_key'],
                    options.ssh_key_path)

            if 'ip_detect' in request.files:
                log.info("Uploading ip-detect script.")
                save_file(
                    request.form['ip_detect'], 
                    options.ip_detect_path)

            if 'master_list' in request.form or 'agent_list' in request.form or 'ssh_user' in request.form or 'ssh_port' in request.form or 'resolvers' in request.form:
                log.info("Uploading and saving new configuration")
                add_config(request, userconfig)
                dump_config(options.config_path, userconfig)

   
        # Ensure the files exist
        config_path_level, config_path_message = ext_helpers.is_path_exists(options.config_path)

        # Validate configuration
        config_level, config_message = validate_for_web(options.config_path)
        isset = get_config(options.config_path)
        dependencies = validate_config(options.config_path)

        return render_template(
            'config.html',
            isset=isset,
            dependencies=dependencies,
            config_level=config_level,
            config_message=config_message,
            config_path_level=config_path_level,
            config_path_message=config_path_message)



    @app.route("/installer/v{}/configurator/generate".format(version),  methods=['POST','GET'])
    def generate():
        from . import generate
        if request.method == 'POST':
            generate.now(options)
            return redirect(redirect_url())       
        
        return redirect(redirect_url())       


    @app.route('/installer/v{}/preflight/'.format(version), methods=['GET','POST'])
    def preflight_check():
        """
        Execute the preflight checks and stream the SSH output back to the 
        web interface.
        """
        if request.method == 'POST':
            log.debug("Kicking off preflight check...")
            from . import preflight
            preflight_validation = preflight.check(options)

            # preflight.check returns the errors from ssh.validate() or False if no
            # errors were returned. Later, we can use this data to drop into a page
            # reload instead of executing the preflight checks. 
            if preflight_validation:
                return redirect(redirect_url())
         
        preflight_data = {}
        for preflight_log in glob('{}/*_preflight.log'.format(options.log_directory)): 
            log_data = yaml.load(open(preflight_log, 'r+'))
            for k, v in log_data.items():
                preflight_data[k] = v

        return render_template(
            'preflight_check.html',
            preflight_data=preflight_data)
   

    
    # Deploy
    @app.route('/installer/v{}/deploy/'.format(version), methods=['POST','GET'])
    def deploy():
        if request.method == 'POST':
            return redirect(redirect_url())

        elif request.method == 'GET':
            return render_template('deploy.html')


def save_file(data, path):
    """
    Save the ip-detect script to the dcos-installer directory.
    """
    log.info("Saving script to %s", path)
    log.debug("Saving file data: %s", data)
    print((str(data)))
    with open(path, 'w') as f:
        f.write(str(data))


def add_config(data, global_data):
    """
    Updates the global userconfig{} map with the latest data from 
    the web console.
    """
    log.info("Adding user config from form POST")
    log.debug("Received raw data: %s", data.form)
    for key in list(data.form.keys()):
        log.debug("%s: %s",key, data.form[key])
        # If the string is actually a list from the POST...
        if len(data.form[key].split(',')) > 1:
            global_data[key] = []
            for value in data.form[key].split(','):
                global_data[key].append(value.rstrip().lstrip())
        else:
            global_data[key] = data.form[key]


def dump_config(path, global_data):
    """
    Dumps our configuration to the config path specific in CLI flags. If the file 
    already exists, add configuration to it from the userconfig presented to us 
    in the web console. Otherwise, if the file does no exist, create it and write the
    config passed to us from the console.
    """

    if os.path.exists(path):
        log.debug("Configuration path exists, reading in and adding config %s", path)
        base_config = yaml.load(open(path, 'r')) 
        try:
            for bk, bv in list(base_config.items()):
                log.debug("Adding configuration from yaml file %s: %s", bk, bv)
                # Overwrite the yaml config with the config from the console
                if not bk in global_data:
                    global_data[bk] = bv
            
            with open(path, 'w') as f:
                f.write(yaml.dump(global_data, default_flow_style=False, explicit_start=True))

        except:
            log.error("Cowardly refusing to write empty data")
            pass

            
    elif not os.path.exists(path):
        with open(path, 'w') as f:
            f.write(yaml.dump(global_data, default_flow_style=False, explicit_start=True))


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



def validate_for_web(path):
    errors, messages = validate_config(path)
    if errors:
        return 'danger', 'Some configuration needs work: {}'.format(messages['errors'])

    else:
        return 'success', 'Configuration looks good!'
        
   
def validate_key_exists(path, key):
    """
    Validate that a key has a value in a config file.
    """
    log.debug("Verifying SSH Key Exists: ", key)
    test_me = get_config(path)
    try:
        if test_me[key] and test_me[key] != '':
            log.debug("%s exists in %s", key, path)
            return "success", '{} exists in {}'.format(key,path)
        elif test_me[key] == '':
            log.debug("%s exists but is empty", key)
            return "warning", '{} exists but is empty'.format(key)
    
    except:
        log.debug("%s not found in %s", key, path)
        return "danger", '{} not found in {}'.format(key, path)



def redirect_url(default='mainpage'):
    return request.args.get('next') or \
        request.referrer or \
        url_for(default)


def validate_config(config_path):
    """
    Defines our redirect logic. In the case of the installer,
    we have several parameters that require other paramters in the tree. 
    This method ensures the user gets redirected to the proper URI based
    on their initial top-level input to the installer.
    """
    if get_config(config_path):
        config = DCOSValidateConfig(get_config(config_path)) 
    else: 
        config = DCOSValidateConfig(userconfig)
    errors, messages = config.validate()
    return errors, messages
