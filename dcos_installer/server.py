from flask import Flask, request, render_template, url_for, redirect
import threading
from glob import glob
import os
import queue
import yaml

# Logging
from dcos_installer.log import DCOSLog
log = DCOSLog(__name__).log

# From dcos-image
#import gen
#from providers import bash
from dcos_installer import copy
from dcos_installer import preflight
from dcos_installer.config import DCOSConfig
from dcos_installer.validate import ext_helpers, DCOSValidateConfig


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



    @app.route("/installer/v{}/".format(version), methods=['GET'])
    def mainpage():
        """
        The mainpage handler
        """
        return render_template('main.html')
    

    # Configurator routes
    @app.route("/installer/v{}/configurator".format(version), methods=['GET', 'POST'])
    def configurator():
        """
        The top level configurator route. This route exposes the two options to go
        to the configurator wizard or to upload the ip script. This will probably
        be changed in the future.
        """
        if request.method == 'POST':
            log.info("POST to configurator...")
            log.info(request)
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

            if 'master_list' in request.form or 'resolvers' in request.form or 'agent_list' in request.form or 'ssh_user' in request.form or 'ssh_port' in request.form:
                log.info("Uploading and saving new configuration")
                add_form_config(request, options.config_path)


        # Ensure the files exist
        config_path_level, config_path_message = ext_helpers.is_path_exists(options.config_path)

        # Validate configuration
        config_level, config_message = validate_for_web(options.config_path)
        isset = get_config(options.config_path)

        return render_template(
            'config.html',
            isset=isset,
            config_level=config_level,
            config_message=config_message,
            config_path_level=config_path_level,
            config_path_message=config_path_message)


    @app.route("/installer/v{}/configurator/clear".format(version), methods=['POST'])
    def clear():
        clean_config(options.config_path)
        return redirect(redirect_url())


    @app.route("/installer/v{}/configurator/generate".format(version),  methods=['POST','GET'])
    def generate():
        # HACKING THIS IN FOR NOW
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
            preflight_queue = queue.Queue()
            p = threading.Thread(target=do_preflight, args=(options, preflight_queue))
            p.daemon = True
            p.start()
            return redirect(redirect_url())

        preflight_data = {}
        for preflight_log in glob('{}/*.log'.format(options.log_directory)): 
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


def do_preflight(options, queue):
    config = get_config(options.config_path)
    queue.put(copy.copy_to_targets(
        config, 
        options.log_directory, 
        '{}/install_dcos.sh'.format(options.serve_directory), 
        '/home/{}'.format(config['ssh_user'])))
    
    queue.put(preflight.check(options, get_config(options.config_path)))

def save_file(data, path):
    """
    Save the ip-detect script to the dcos-installer directory.
    """
    log.info("Saving script to %s", path)
    log.debug("Saving file data: %s", data)
    print((str(data)))
    with open(path, 'w') as f:
        f.write(str(data))


def add_form_config(data, path):
    """
    Updates the global userconfig{} map with the latest data from 
    the web console.
    """
    log.info("Adding configuration...")
    
    # Turn form data from POST into dict for DCOSConfig overrides
    new_data = {}
    current_config = get_config(path)
    if current_config:
        for k, v in current_config.items():
            new_data[k] = v
        
    for key in list(data.form.keys()):
        log.debug("%s: %s",key, data.form[key])
        if key in ['resolvers', 'master_list', 'cluster_name']:
            if len(data.form[key]) > 0:
                # If the string is actually a list from the POST...
                if len(data.form[key].split(',')) > 1:
                    new_data['cluster_config'][key] = []
                    for value in data.form[key].split(','):
                        new_data['cluster_config'][key].append(value.rstrip().lstrip())
                else:
                    # master and agent list have to always be an array
                    if key == 'master_list':
                        new_data['cluster_config'][key] = [data.form[key]]
                    
                    else:
                        new_data['cluster_config'][key] = data.form[key]

            else:
                log.info("Refusing to write null data for %s", key)

        elif key in ['target_hosts', 'ssh_user', 'ssh_port']:
            if len(data.form[key]) > 0:
                # If the string is actually a list from the POST...
                if len(data.form[key].split(',')) > 1:
                    new_data['ssh_config'][key] = []
                    for value in data.form[key].split(','):
                        new_data['ssh_config'][key].append(value.rstrip().lstrip())
                else:
                    # master and agent list have to always be an array
                    if key == 'agent_list':
                        new_data['ssh_config'][key] = [data.form[key]]
                    
                    else:
                        new_data['ssh_config'][key] = data.form[key]

            else:
                log.info("Refusing to write null data for %s", key)

    
    config = DCOSConfig(overrides=new_data, config_path=path)
    # Deserialize the class pieces we want since cnfig and overrides end up in dict
    write_config(unbind_configuration(config), path)


def unbind_configuration(data):
    """
    Unbinds the methods and class variables from the DCOSConfig
    object and returns a simple dictionary.
    """
    dictionary = {}
    for k, v in data.items():
        dictionary[k] = v

    return dictionary

   
def write_config(config, path):
    log.info("NEW CONFIGURATION WRITTEN:")
    log.info(config)
    with open(path, 'w') as f:
        f.write(yaml.dump(config, default_flow_style=False, explicit_start=True))
    
  
def redirect_url(default='mainpage'):
    return request.args.get('next') or \
        request.referrer or \
        url_for(default)


def get_config(path):
    """
    Returns the config file as a dict.
    """
    if os.path.exists(path):
        config = yaml.load(open(path, 'r'))
    
    else: 
        config = {}

    return config


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
        return 'danger', messages['errors']

    else:
        return 'success', 'Configuration looks good!'


def validate_config(config_path):
    """
    Defines our redirect logic. In the case of the installer,
    we have several parameters that require other paramters in the tree. 
    This method ensures the user gets redirected to the proper URI based
    on their initial top-level input to the installer.
    """
    if get_config(config_path):
        config = DCOSValidateConfig(get_config(config_path)) 
        errors, messages = config.validate()
    
    else: 
        # If not found, write defualts
        log.error('Configuration file not found, setting default config.')
        default_config = DCOSConfig()
        write_config(unbind_configuration(default_config), config_path)
        
        # Validate new default config
        config = DCOSValidateConfig(get_config(config_path)) 
        errors, messages = config.validate()

    return errors, messages
