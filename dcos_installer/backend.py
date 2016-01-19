"""
Glue code for logic around calling associated backend
libraries to support the dcos installer.
"""
import logging

from dcos_installer.config import DCOSConfig
from dcos_installer.util import CONFIG_PATH

from deploy.util import create_agent_list
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
    config_obj = DCOSConfig(config_path=CONFIG_PATH, post_data=post_data)

    log.warning("Updated config to be validated:")
    config_obj.print_to_screen()

    messages = config_obj.validate()

    config_obj.write()
    return messages


def get_config():
    return DCOSConfig(config_path=CONFIG_PATH).get_config()


def success():
    """
    Return the success URL, master and agent counts.
    """
    # TODO(malnick) implement with DCOSConfig constructor
    data = DCOSConfig(config_path=CONFIG_PATH).get_config()
    url = 'http://{}'.format(data['cluster_config']['master_list'][0])
    master_count = len(data['cluster_config']['master_list'])
    agent_count = len(create_agent_list(data))

    return_success = {
        'success': url,
        'master_count': master_count,
        'agent_count': agent_count
    }

    return return_success
