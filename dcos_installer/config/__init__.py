# Configuration loader for dcosgen
# Set all configuration for a given run with a simple map
# my_opts = {
#     'config_dir':  '/tmp'
# }
#
# c = DcosConfig()
# print(c)

import json
import logging
import os
import yaml

from dcos_installer.validate import DCOSValidateConfig
log = logging.getLogger(__name__)


class DCOSConfig(dict):
    """
    Return the site configuration object for dcosgen library
    """
    def __init__(self, overrides={}, config_path=None):
        defaults = """
---
cluster_config:
  cluster_name: 'Mesosphere: The Data Center Operating System'
  ip_detect_path: /genconf/ip-detect
  num_masters:
  master_discovery: static
  master_list:
  exhibitor_storage_backend: zookeeper
  exhibitor_zk_hosts: 127.0.0.1:2181
  exhibitor_zk_path: /exhibitor
  weights: slave_public=1
  bootstrap_url: file:///opt/dcos_install_tmp
  roles: slave_public
  docker_remove_delay: 1hrs
  gc_delay: 2days
  resolvers:
    - 8.8.8.8
    - 8.8.4.4

ssh_config:
  target_hosts:
  -
  ssh_user:
  ssh_port: 22
  ssh_key_path: /genconf/ssh_key
  log_directory: /genconf/logs
"""
        self.defaults = yaml.load(defaults)
        # We're using the on-container /genconf directory for v1 of the installer, these are unneccessary for now
        # self.defaults['ssh_config']['ssh_key_path'] = '{}/dcos-installer/ssh_key'.format(os.path.expanduser('~'))
        # self.defaults['cluster_config']['config_dir'] = '{}/dcos-installer'.format(os.path.expanduser('~'))
        # self.defaults['cluster_config']['ip_detect_path'] =
        # '{}/dcos-installer/ip-detect'.format(os.path.expanduser('~'))
        # Setting the passed in options as the overrides for the instance of the class.
        self.config_path = config_path
        self.overrides = overrides
        self._update()

        log.debug("Configuration:")
        for k, v in self.items():
            log.debug("%s: %s", k, v)

    def _update(self):
        # Create defaults
        for key, value in self.defaults.items():
            self[key] = value
        # Get user config file configuration
        if self.config_path:
            user_config = self.load_user_config(self.config_path)
            # Add user-land configuration
            if user_config:
                for k, v in user_config.items():
                    self[k] = v
            else:
                log.warning("No user configuration found, using all defaults.")

        # Add user config if any
        if self.overrides is not None and len(self.overrides) > 0:
            for key, value in self.overrides.items():
                if isinstance(value, dict):
                    for k1, v1 in value.items():
                        log.warning("Overriding %s with %s", self[key][k1], v1)
                        self[key][k1] = v1

        # Update num_masters and target_hosts with master_list data
        print("self", self)
        if self['cluster_config']['master_list']:
            self['cluster_config']['num_masters'] = len(self['cluster_config']['master_list'])
            if self['cluster_config']['master_list'] is not None:
                for ip in self['cluster_config']['master_list']:
                    if ip not in self['ssh_config']['target_hosts']:
                        self['ssh_config']['target_hosts'].append(ip)

    def validate(self):
        # Convienience function to validate this object
        _, messages = DCOSValidateConfig(self).validate()
        return messages

    def load_user_config(self, config_path):
        """
        Load user-land configuration and exit upon errors.
        """
        if os.path.isfile(config_path):
            log.debug("%s exists.", config_path)
            if config_path.endswith('.json'):
                log.debug("Loading JSON configuration: %s", config_path)
                with open(config_path, 'r') as data:
                    return json.load(data)

            elif config_path.endswith('.yaml'):
                log.debug("Loading YAML configuration: %s", config_path)
                with open(config_path, 'r') as data:
                    return yaml.load(data)

            else:
                log.error("Configuration file is not a type I can use.")
                log.error("Acceptable types: JSON or YAML.")
                pass

        else:
            log.error("Configuration file not found, %s", config_path)
            log.warn("Using ALL DEFAULT configuration since %s was not found.", config_path)
            self.write(self.defaults, config_path)
            return yaml.load(open(config_path, 'r'))

    def write(self, config_path):
        data = open(config_path, 'w')
        data.write(yaml.dump(self.unbind_configuration(), default_flow_style=False, explicit_start=True))
        data.close()

    def unbind_configuration(self):
        """
        Unbinds the methods and class variables from the DCOSConfig
        object and returns a simple dictionary.
        """
        dictionary = {}
        for k, v in self.items():
            dictionary[k] = v

        return dictionary
