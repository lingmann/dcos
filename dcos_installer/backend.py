"""
Glue code for logic around calling associated backend
libraries to support the dcos installer.
"""
from dcos_installer.mock import mock_config_yaml

import yaml

from deploy.util import create_agent_list
from providers.genconf import do_genconf


def configure():
    do_genconf(interactive=False)


def success():
    """
    Return the success URL, master and agent counts.
    """
    # TODO(malnick) implement with DCOSConfig constructor
    yaml_data = yaml.load(mock_config_yaml)
    url = 'http://foobar.org'
    master_count = len(yaml_data['cluster_config']['master_list'])
    agent_count = len(create_agent_list(yaml_data))

    return_success = {
        'success': url,
        'master_count': master_count,
        'agent_count': agent_count
    }

    return return_success
