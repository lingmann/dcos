"""
Glue code for logic around calling associated backend
libraries to support the dcos installer.
"""
import logging
import os

from dcos_installer.config import DCOSConfig
from dcos_installer.util import CONFIG_PATH

# Need to build a new provider for config generation from installer
from providers.genconf import do_genconf

log = logging.getLogger()


def generate_configuration():
    do_genconf(interactive=False)


def create_config_from_post(post_data):
    """
    Take POST data and form it into the dual dictionary we need
    to pass it as overrides to DCOSConfig object.
    """
    log.info("Creating new DCOSConfig object from POST data.")
    val_config_obj = DCOSConfig(config_path=CONFIG_PATH, overrides=post_data)
    messages = val_config_obj.validate()

    log.warning("Updated config to be validated:")
    val_config_obj.print_to_screen()
    # Return only keys sent in POST
    return_messages = {}
    validation_err = False
    if len(messages['errors']) > 0:
        log.warning("Errors in POSTed configuration.")
        return_messages = {param: messages['errors'][param] for param in messages['errors'] if param in post_data}
        validation_err = True

    val_config_obj.write()
    return validation_err, return_messages


def get_config():
    return DCOSConfig(config_path=CONFIG_PATH).get_config()


def return_configure_status():
    """
    Read configuration from disk and return validation messages.
    """
    messages = DCOSConfig(config_path=CONFIG_PATH).validate()
    return messages


def determine_config_type():
    """
    Return the configuration type to HTTP endpoint. Possible types are
    minimal and advanced. Messages are blank for minimal and detailed
    in the case of advanced so we can warn users they need to remove the
    current advanced config before moving on.
    """
    config = get_config()
    ctype = 'minimal'
    message = ''
    adv_found = {}
    advanced_cluster_config = {
        "bootstrap_url": None,
        "docker_remove_delay": None,
        "exhibitor_storage_backend": 'zookeeper',
        "exhibitor_zk_path": None,
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
            adv_found[key] = config[key]

    if len(adv_found) > 0:
        message = """Advanced configuration detected in genconf/config.yaml ({}).
 Please backup or remove genconf/config.yaml to use the UI installer.""".format(adv_found)
        ctype = 'advanced'

    return {
        'message': message,
        'type': ctype
    }


def success():
    """
    Return the success URL, master and agent counts.
    """
    # TODO(malnick) implement with DCOSConfig constructor
    data = DCOSConfig(config_path=CONFIG_PATH).get_config()
    url = 'http://{}'.format(data['master_list'][0])
    master_count = len(data['master_list'])
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
