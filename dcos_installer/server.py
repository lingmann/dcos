import os
from glob import glob

import yaml
from dcos_installer.log import DCOSLog
log = DCOSLog(__name__).log

# From dcos-image
#import gen
#from providers import bash

# Helper submodules
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

<<<<<<< HEAD
    @app.route("/installer/v{}/configurator/clear".format(version), methods=['POST'])
    def clear():
        clean_config(options.config_path)
        return redirect(redirect_url())
=======

>>>>>>> ssh_consolidation

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
<<<<<<< HEAD
        config_level, config_message = validate(options.config_path)
        ip_detect_level, ip_detect_message = validate_path(options.ip_detect_path)
        return render_template(
            'configurator.html',
            config_level=config_level,
            config_message=config_message,
            ip_detect_message=ip_detect_message,
            ip_detect_level=ip_detect_level)

    @app.route("/installer/v{}/configurator/ip-detect/".format(version),  methods=['GET', 'POST'])
    def ip_detect():
        save_to_path = options.ip_detect_path
        if request.method == 'POST':
            save_file(
                request.form['ip_detect'],
                save_to_path)
            # TODO: basic ip-detect script validation
=======
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

            if 'master_list' in request.form or 'agent_list' in request.form or 'ssh_user' in request.form or 'ssh_port' in request.form or 'resolvers' in request.form:
                log.info("Uploading and saving new configuration")
                add_form_config(request, options.config_path)

   
        # Ensure the files exist
        config_path_level, config_path_message = ext_helpers.is_path_exists(options.config_path)
>>>>>>> ssh_consolidation

        # Validate configuration
        config_level, config_message = validate_for_web(options.config_path)
        isset = get_config(options.config_path)

        return render_template(
<<<<<<< HEAD
            'ip_detect.html',
            validate_level=validate_level,
            validate_message=message)
=======
            'config.html',
            isset=isset,
            config_level=config_level,
            config_message=config_message,
            config_path_level=config_path_level,
            config_path_message=config_path_message)
>>>>>>> ssh_consolidation


<<<<<<< HEAD
        level, message = validate(options.config_path)
        return render_template(
            'config.html',
            isset=get_config(options.config_path),
            dependencies=get_dependencies(options.config_path),
            validate_level=level,
            validate_message=message)
=======
    @app.route("/installer/v{}/configurator/clear".format(version), methods=['POST'])
    def clear():
        clean_config(options.config_path)
        return redirect(redirect_url())

>>>>>>> ssh_consolidation

    @app.route("/installer/v{}/configurator/generate".format(version), methods=['POST', 'GET'])
    def generate():
        from . import generate
        if request.method == 'POST':
            generate.now(options)
            return redirect(redirect_url())
        return redirect(redirect_url())

<<<<<<< HEAD
    # Preflight
    @app.route("/installer/v{}/preflight/".format(version),  methods=['GET', 'POST'])
    def preflight():
        """
        If the request is a POST, check for the preflight_check form key. If that key exists
        execute the preflight.check library. If it doesn't, save hosts.yaml config. If
        the method is a GET, serve the template.
        """
        if request.method == 'POST':
            """
            If request is a POST then we assume it's updating the hosts.yaml.
            """
            add_config(request, hostsconfig)
            dump_config(options.hosts_yaml_path, hostsconfig)
            # TODO: basic host validation??

        # Validate hosts file, ssh key file and ssh username file
        validate_hosts_level, hosts_message = validate_hosts(options.hosts_yaml_path)
        validate_ssh_level, validate_ssh_message = validate_path(options.ssh_key_path)
        validate_user_level, validate_user_message = validate_path(options.ssh_user_path)

        return render_template(
            'preflight.html',
            isset=get_config('{}/hosts.yaml'.format(options.install_directory)),
            validate_hosts_level=validate_hosts_level,
            validate_hosts_message=hosts_message,
            validate_ssh_level=validate_ssh_level,
            validate_ssh_message=validate_ssh_message,
            validate_user_level=validate_user_level,
            validate_user_message=validate_user_message)

    @app.route('/installer/v{}/preflight/check/'.format(version), methods=['GET', 'POST'])
=======
    @app.route('/installer/v{}/preflight/'.format(version), methods=['GET','POST'])
>>>>>>> ssh_consolidation
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

<<<<<<< HEAD
    @app.route('/installer/v{}/preflight/ssh_key/'.format(version), methods=['POST'])
    def preflight_ssh_key():
        ssh_key_path = options.ssh_key_path
        ssh_user_path = options.ssh_user_path
        print((request.files))
        if 'ssh_user' in request.form:
            log.info("Adding SSH user %s", request.form['ssh_user'])
            save_file(
                request.form['ssh_user'],
                ssh_user_path)
        elif 'ssh_key' in request.files:
            log.info("Adding SSH key")
            save_file(
                request.files['ssh_key'],
                ssh_key_path)
        else:
            log.error("Unknown POST to /ssh_key route.")
            pass
        return redirect(redirect_url())

    # TODO Move hosts down here too

=======
    
>>>>>>> ssh_consolidation
    # Deploy
    @app.route('/installer/v{}/deploy/'.format(version), methods=['POST', 'GET'])
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
<<<<<<< HEAD
        log.debug("%s: %s", key, data.form[key])
        # If the string is actually a list from the POST...
        if len(data.form[key].split(',')) > 1:
            global_data[key] = []
            for value in data.form[key].split(','):
                global_data[key].append(value.rstrip().lstrip())
=======
        log.debug("%s: %s",key, data.form[key])
        if len(data.form[key]) > 0:
            # If the string is actually a list from the POST...
            if len(data.form[key].split(',')) > 1:
                new_data[key] = []
                for value in data.form[key].split(','):
                    new_data[key].append(value.rstrip().lstrip())
            else:
                new_data[key] = data.form[key]
>>>>>>> ssh_consolidation
        else:
            log.info("Refusing to write null data for %s", key)

    
    config = DCOSConfig(overrides=new_data, config_path=path)
    # Deserialize the class pieces we want since cnfig and overrides end up in dict
    write_config(unbind_configuration(config), path)


def unbind_configuration(data):
    """
<<<<<<< HEAD
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
                if bk not in global_data:
                    global_data[bk] = bv
            with open(path, 'w') as f:
                f.write(yaml.dump(global_data, default_flow_style=False, explicit_start=True))
        except:
            log.error("Cowardly refusing to write empty data")
            pass
    elif not os.path.exists(path):
        with open(path, 'w') as f:
            f.write(yaml.dump(global_data, default_flow_style=False, explicit_start=True))
=======
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
>>>>>>> ssh_consolidation


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
 

<<<<<<< HEAD

def validate(path):
    config = get_config(path)
    missing_deps = []
    if config != {}:
        dependencies = get_dependencies(path)
        log.debug("Validating configruation file %s...", path)
        for dk, dv in list(dependencies.items()):
            log.debug("Checking coniguration for %s", dk)
            for required_value in dv:
                log.debug("Ensuring dependency %s exists in config", required_value)
                # Ensure the key for the dependency exists
                if required_value not in config:
                    log.warning("Unfound value for %s: %s", path, required_value)
                    missing_deps.append(required_value)
                    continue
                    # return "danger", 'Configuation for {} is not set.'.format(required_value)

                # Make sure not keys have nil / blank values
                elif required_value in config:
                    if not len(config[required_value]) > 0:
                        log.warning("Value found is not set for key %s", required_value)
                        missing_deps.append(required_value)
                        # return "danger", 'Configuration for {} is not set.'.format(required_value)
                        continue
                # I hate not having switch statements...
                # Fall through to continue on values found and not being nil
                else:
                    continue

        if len(missing_deps) > 0:
            log.warning("Configuration for %s not found.", missing_deps)
            return 'danger', 'Missing configuration parameters: {}'.format(missing_deps)
        else:
            log.info("Configuration looks good!")
            return "success", "Configuration looks good!"
    else:
        log.warning("Configuration file is empty")
        return "warning", "Configuration file appears empty."


def validate_path(path):
    """
    Validate the ip-detect script exists and report back.
    """
    if os.path.exists(path):
        return "success", 'File exists {}'.format(path)
=======
def validate_for_web(path):
    errors, messages = validate_config(path)
    if errors:
        return 'danger', messages['errors']

>>>>>>> ssh_consolidation
    else:
        return 'success', 'Configuration looks good!'


<<<<<<< HEAD
def validate_key_exists(path, key):
    """
    Validate that a key has a value in a config file.
    """
    log.debug("Testing %s", key)
    test_me = get_config(path)
    try:
        if test_me[key] and test_me[key] != '':
            log.debug("%s exists in %s", key, path)
            return "success", '{} exists in {}'.format(key, path)
        elif test_me[key] == '':
            log.debug("%s exists but is empty", key)
            return "warning", '{} existt but is empty'.format(key)
    except:
        log.debug("%s not found in %s", key, path)
        return "danger", '{} not found in {}'.format(key, path)


def validate_hosts(path):
    """
    Validate that the host file exists and the keys are available.
    """
    if validate_path(path) == 'danger':
        return 'danger', 'hosts.yaml does not exist: {}'.format(path)
    for key in ['ssh_user', 'ssh_key_path', 'master', 'slave_public', 'slave_private']:    
        validation, message = validate_key_exists(path, key)
        # Catch dangers first
        if validation == 'danger':
            return validation, message
        # Catch warnings last
        if validation == 'warning':
            return validation, message
        else:
            return validation, 'hosts.yaml looks good!'


def redirect_url(default='mainpage'):
    return request.args.get('next') or \
        request.referrer or \
        url_for(default)


def get_dependencies(config_path):
=======
def validate_config(config_path):
>>>>>>> ssh_consolidation
    """
    Defines our redirect logic. In the case of the installer,
    we have several parameters that require other paramters in the tree.
    This method ensures the user gets redirected to the proper URI based
    on their initial top-level input to the installer.
    """
<<<<<<< HEAD
    config = get_config(config_path)

    dep_tree = {
        "master_discovery": {
            "static":  ["master_list"],
            "keepalived": ["keepalived_router_id",
                           "keepalived_interface",
                           "keepalived_pass",
                           "keepalived_virtual_ipaddress"],
            "cloud_dynamic": ["num_masters"],
        },
        "exhibitor_storage_backend": {
            "zookeeper": ["exhibitor_zk_hosts", "exhibitor_zk_path"],
            "shared_filesystem": ["exhibitor_fs_config_dir"],
            "aws_s3": ["aws_access_key_id",
                       "aws_secret_access_key",
                       "aws_region",
                       "s3_bucket",
                       "s3_prefix"],
        },
        "base": {
            "master_discovery": "",
            "exhibitor_storage_backend": "",
            "cluster_name": "",
            "resolvers": "",
            "weights": "",
            "bootstrap_url": "",
            "roles": "",
            "docker_remove_delay": "",
            "gc_delay": ""
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
    esb = 'exhibitor_storage_backend'
    if config.get(esb):
        try:
            return_deps[esb] = dep_tree[esb][config[esb]]
        except:
            log.error("The specified configuration value is not valid, %s", config[esb])
=======
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
>>>>>>> ssh_consolidation

    return errors, messages
