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
from dcos_installer.util import CONFIG_PATH, SSH_KEY_PATH, IP_DETECT_PATH
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
-

# The IPv4 addresses of your agent hosts
agent_list:
-

# The bootstrapping exhibitor hosts. Format is ip:port.
exhibitor_zk_hosts:

# Upstream DNS resolvers for MesosDNS
resolvers:
- 8.8.8.8
- 8.8.4.4

# DCOS username and password
username:
password:

ssh_user:
ssh_port: 22
process_timeout: 120

bootstrap_url: file:///opt/dcos_install_tmp
"""
        self.defaults = yaml.load(defaults)
        self.config_path = config_path
        # These are defaults we do not want to expose to the user, but still need
        # to be included in validation for return. We never write them to disk.
        self.hidden_defaults = {
            'ip_detect_path':  IP_DETECT_PATH,
            'ssh_key_path': SSH_KEY_PATH,
        }
        self.overrides = overrides
        self.update()
        self.errors = []

        log.debug("Configuration:")
        for k, v in self.items():
            log.debug("%s: %s", k, v)

    def update(self):
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

        self._add_overrides()

    def _add_overrides(self):
        """
        Add overrides. Overrides expects data in the same format as the config file.
        """
        arrays = ['master_list', 'resolvers', 'target_hosts']
        if self.overrides is not None and len(self.overrides) > 0:
            for key, value in self.overrides.items():
                if key == 'ssh_key':
                    self.write_to_disk(value, SSH_KEY_PATH)

                if key == 'ip_detect_script':
                    self.write_to_disk(value, IP_DETECT_PATH)

                if key in arrays and value is None:
                    log.warning("Overriding %s: %s -> %s", key, self[key], value)
                    self[key] = list(value)
                elif key in self:
                    log.warning("Overriding %s: %s -> %s", key, self[key], value)
                    self[key] = value

    def validate(self):
        # TODO Leverage Gen library from here
        # Convienience function to validate this object
        file_config = self._unbind_configuration()
        hidden_config = self.hidden_defaults
        validate_config = dict(file_config, **hidden_config)
        log.warning(validate_config)
        _, messages = DCOSValidateConfig(validate_config).validate()
        return messages

    def get_config(self):
        """
        Load user-land configuration and exit upon errors.
        """
        if os.path.isfile(self.config_path):
            log.debug("Loading YAML configuration: %s", self.config_path)
            with open(self.config_path, 'r') as data:
                return yaml.load(data)

        log.error(
            "Configuration file not found, %s. Writing new one with all defaults.",
            self.config_path)
        self.config_path = CONFIG_PATH
        self.write()
        return yaml.load(open(self.config_path))

    def write(self):
        if self.config_path:
            data = open(self.config_path, 'w')
            data.write(yaml.dump(self._unbind_configuration(), default_flow_style=False, explicit_start=True))
            data.close()
        else:
            log.error("Must pass config_path=/path/to/file to execute .write().")

    def write_to_disk(self, data, path):
        log.warning("Writing %s to %s.", path, SSH_KEY_PATH)
        f = open(path, 'w')
        f.write(data)

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
