# Configuration loader for dcosgen
# Set all configuration for a given run with a simple map
# my_opts = {
#     'config_dir':  '/tmp'
# }
#
# c = DcosConfig()
# print(c)
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
# The name of your DCOS cluster. Visable in the DCOS user interface.
cluster_name: 'Mesosphere: The Data Center Operating System'

# The IPv4 addresses of your master hosts
master_list:
- 127.0.0.1

# The IPv4 addresses of your agent hosts
agent_list:
- 127.0.0.1

# The bootstrapping exhibitor hosts. Format is ip:port.
exhibitor_zk_hosts: 127.0.0.1:2181

# Upstream DNS resolvers for MesosDNS
resolvers:
- 8.8.8.8
- 8.8.4.4

ssh_key_path: /genconf/ssh_key
log_directory: /genconf/logs
ip_detect_path: /genconf/ip-detect

ssh_user: centos
ssh_port: 22
process_timeout: 120

# Optional parameter for executing SSH with an attached TTY. Useful in
# AWS or other environments which require a tty with your ssh session
# to execute sudo on remote machines.
extra_ssh_options: -tt
"""
        # TODO set this to validate()? What does validate return? messages,config?
        self.defaults = yaml.load(defaults)
        self.config_path = config_path
        self.overrides = overrides
        self._update()
        self.errors = []

        log.debug("Configuration:")
        for k, v in self.items():
            log.debug("%s: %s", k, v)

    def _update(self):
        # Create defaults
        for key, value in self.defaults.items():
            self[key] = value
        # Get user config file configuration
        if self.config_path:
            user_config = self.get_config()
            # Add user-land configuration
            if user_config:
                for k, v in user_config.items():
                    self[k] = v

        # Add overrides, if any
        self._add_overrides()

    def _add_overrides(self):
        """
        Add overrides. Overrides expects data in the same format as the config file.
        """
        arrays = ['master_list', 'resolvers', 'target_hosts']
        if self.overrides is not None and len(self.overrides) > 0:
            for key, value in self.overrides.items():
                    log.warning("Overriding %s: %s -> %s", key, self[key], value)
                    if key in arrays and value is None:
                        self[key] = list(value)
                    else:
                        self[key] = value

    def validate(self):
        # TODO Leverage Gen library from here
        # Convienience function to validate this object
        _, messages = DCOSValidateConfig(self).validate()
        print(messages)
        return messages

    def get_config(self):
        """
        Load user-land configuration and exit upon errors.
        """
        if os.path.isfile(self.config_path):
            log.debug("Loading YAML configuration: %s", self.config_path)
            with open(self.config_path, 'r') as data:
                return yaml.load(data)

        log.error("Configuration file not found, %s. Writing new one with all defaults.", self.config_path)
        self.write()
        return yaml.load(open(self.config_path))

    def write(self):
        if self.config_path:
            data = open(self.config_path, 'w')
            data.write(yaml.dump(self._unbind_configuration(), default_flow_style=False, explicit_start=True))
            data.close()
        else:
            log.error("Must pass config_path=/path/to/file to execute .write().")

    def print_to_screen(self):
        print(yaml.dump(self._unbind_configuration(), default_flow_style=False, explicit_start=True))

    def _unbind_configuration(self):
        """
        Unbinds the methods and class variables from the DCOSConfig
        object and returns a simple dictionary.
        """
        dictionary = {}
        for k, v in self.items():
            dictionary[k] = v

        return dictionary
