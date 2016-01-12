import logging

from dcos_installer.config import DCOSConfig

from deploy.util import create_agent_list

import yaml

log = logging.getLogger(__name__)

mock_action_state = {
    "10.0.0.1": {
        "role": "master",
        "state": "not_running",
        "cmd": "",
        "returncode": -1,
        "stderr": [""],
        "stdout": [""]
    },
    "10.0.0.2": {
        "role": "slave",
        "state": "running",
        "cmd": "",
        "returncode": -1,
        "stderr": [""],
        "stdout": [""]
    },
    "10.0.0.3": {
        "role": "slave",
        "state": "not_running",
        "cmd": "",
        "returncode": -1,
        "stderr": [""],
        "stdout": [""]
    },
    "10.0.0.4": {
        "role": "slave",
        "state": "success",
        "cmd": "",
        "returncode": -1,
        "stderr": [""],
        "stdout": [""]
    },
    "10.0.0.5": {
        "role": "slave",
        "state": "error",
        "cmd": "",
        "returncode": -1,
        "stderr": [""],
        "stdout": [""]
    }
}

mock_config_yaml = """
---
cluster_config:
  bootstrap_url: file:///opt/dcos_install_tmp
  cluster_name: 'Mesosphere: The Data Center Operating System'
  docker_remove_delay: 1hrs
  exhibitor_storage_backend: zookeeper
  exhibitor_zk_hosts: 127.0.0.1:2181
  exhibitor_zk_path: /exhibitor
  gc_delay: 2days
  ip_detect_path: /genconf/ip-detect
  master_discovery: static
  master_list:
  - 10.0.0.1
  - 10.0.0.2
  - 10.0.0.3
  num_masters: null
  resolvers:
  - 8.8.8.8
  - 8.8.4.4
  roles: slave_public
  weights: slave_public=1
ssh_config:
  log_directory: /genconf/logs
  ssh_key_path: /genconf/ssh_key
  ssh_port: 22
  ssh_user: foobar
  target_hosts:
  - 10.0.0.1
  - 10.0.0.2
  - 10.0.0.3
  - 10.0.0.4
  - 10.0.0.5
  - 10.0.0.6
  - 10.0.0.7
  - 10.0.0.8
"""


def get_config():
    yaml_data = yaml.load(mock_config_yaml)
    return yaml_data


def mock_success():
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


def validate(new_data={}):
    """
    Take the new data from a post, add it to base defaults if overwritting them
    and validate the entire config, return messages.
    If the new_data is empty, return the pure defualts for the config. This is in
    place of having a known file system that we're writing to for config.yaml, in
    which case we'd pass the config_path option to DCOSConfig so it uses those
    instead of the defualts. For now, the mock version will return only defualts
    on GET and return the complete config with overrides on POST.
    """
    config = DCOSConfig(overrides=new_data, config_path='/tmp/config.yaml')
    log.info("New Config:")
    print(yaml.dump(config, default_flow_style=False, explicit_start=True))
    messages = config.validate()
    # TODO write configuration back to disk, leaving out for now for test
    # write_config(unbind_configuration(config), 'config.yaml')
    return messages, config


def write_config(config, path, dcosconfig_obj):
    dcosconfig_obj.write_config(path)


def unbind_configuration(data):
    """
    Unbinds the methods and class variables from the DCOSConfig
    object and returns a simple dictionary.
    """
    dictionary = {}
    for k, v in data.items():
        dictionary[k] = v

    return dictionary
