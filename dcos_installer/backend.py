"""
Glue code for logic around calling associated backend
libraries to support the dcos installer.
"""
import logging
import os

#from dcos_installer.action_lib import configure
from dcos_installer.config import DCOSConfig
from dcos_installer.util import CONFIG_PATH

log = logging.getLogger()


def do_configure():
    pass
#    configure.do_configure()


def create_config_from_post(post_data={}, config_path=CONFIG_PATH):
    """
    Take POST data and form it into the dual dictionary we need
    to pass it as overrides to DCOSConfig object.
    """
    log.info("Creating new DCOSConfig object from POST data.")
    # Get a blank config file object
    val_config_obj = DCOSConfig()
    # If the config file does not exist, write it.
    if not os.path.exists(config_path):
        log.warning('{} not found, writing default configuration.'.format(config_path))
        val_config_obj.config_path = config_path
        val_config_obj.write()

    # Add overrides from POST to config
    val_config_obj.overrides = post_data
    val_config_obj.config_path = CONFIG_PATH
    val_config_obj.update()
    messages = val_config_obj.validate()

    log.warning("Updated config to be validated:")
    val_config_obj.print_to_screen()

    # Return only keys sent in POST, do not write if validation
    # of config fails.
    validation_err = False

    # Create a dictionary of validation that only includes
    # the messages from keys POSTed for validation.
    post_data_validation = {param: messages['errors'][param] for param in messages['errors'] if param in post_data}

    # If validation is successful, write the data to disk, otherwise, if
    # they keys POSTed failed, do not write to disk.
    if len(post_data_validation) > 0:
        log.warning("POSTed configuration has errors, not writing to disk.")
        for key, value in post_data_validation.items():
            log.error('{}: {}'.format(key, value))
        validation_err = True

    else:
        log.info("Success! POSTed configuration looks good, writing to disk.")
        val_config_obj.config_path = config_path
        val_config_obj.write()

    return validation_err, post_data_validation


def get_config(config_path=CONFIG_PATH):
    return DCOSConfig(config_path=config_path).get_config()


def return_configure_status(config_path=CONFIG_PATH):
    """
    Read configuration from disk and return validation messages.
    """
    messages = DCOSConfig(config_path=config_path).validate()
    return messages


def determine_config_type(config_path=CONFIG_PATH):
    """
    Return the configuration type to HTTP endpoint. Possible types are
    minimal and advanced. Messages are blank for minimal and detailed
    in the case of advanced so we can warn users they need to remove the
    current advanced config before moving on.
    """
    config = get_config(config_path=config_path)
    ctype = 'minimal'
    message = ''
    adv_found = {}
    advanced_cluster_config = {
        "bootstrap_url": 'file:///opt/dcos_install_tmp',
        "docker_remove_delay": None,
        "exhibitor_storage_backend": 'zookeeper',
        "gc_delay": None,
        "master_discovery": 'static',
        "roles": None,
        "weights": None
    }
    for key, value in advanced_cluster_config.items():
        # If the key is present in the config but we don't care what
        # the default is, add it to the advanced found hash.
        if value is None and key in config:
            adv_found[key] = config[key]

        # If the key is present in the config and we do care what the
        # value is set to, and the value present in the config is not
        # what we want it to be, add it to adv config hash.
        if value is not None and key in config and value != config[key]:
            log.error('Advanced configuration found in config.yaml: {}: value'.format(key, value))
            adv_found[key] = config[key]

    if len(adv_found) > 0:
        message = """Advanced configuration detected in genconf/config.yaml ({}).
 Please backup or remove genconf/config.yaml to use the UI installer.""".format(adv_found)
        ctype = 'advanced'

    return {
        'message': message,
        'type': ctype
    }


def success(config_path=CONFIG_PATH):
    """
    Return the success URL, master and agent counts.
    """
    data = get_config(config_path=config_path)
    # The config file will have None by default, but just in
    # case we're setting it here to default.
    master_ips = data.get('master_list', None)
    agent_ips = data.get('agent_list', None)
    url = 'http://{}'.format(master_ips[0])
    master_count = 0
    agent_count = 0

    if master_ips[0] is not None:
        master_count = len(data['master_list'])

    if agent_ips[0] is not None:
        agent_count = len(data['agent_list'])

    return_success = {
        'success': url,
        'master_count': master_count,
        'agent_count': agent_count
    }

    return return_success


def make_default_directories():
    """
    So users do not have to set the directories in the config.yaml,
    we build them using sane defaults here first.
    """
    config = get_config()
    state_dir = config['state_dir'].get('state_dir', '/genconf/state')
    if not os.path.exists(state_dir):
        os.makedirs(state_dir)
