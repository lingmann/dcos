"""
Configuration loader for dcosgen
Set all configuration for a given run with a simple map
my_opts = {
    'config_dir':  '/tmp'
}

c = DcosConfig()
print(c)
"""
import json
import logging
import os
import yaml

from dcos_installer.validate import DCOSValidateConfig
from dcos_installer.util import CONFIG_PATH, SSH_KEY_PATH, IP_DETECT_PATH, REXRAY_CONFIG_PATH
log = logging.getLogger(__name__)


class DCOSConfig(dict):
    """
    Return the site configuration object for dcosgen library
    """
    def __init__(self, overrides={}, config_path=CONFIG_PATH, write_default_config=True):
        defaults = """
---
# The name of your DCOS cluster. Visable in the DCOS user interface.
cluster_name: 'DCOS'

# Master discovery must be static
master_discovery: static

# The IPv4 addresses of your master hosts
master_list:
-

# The IPv4 addresses of your agent hosts
agent_list:
-

# The bootstrapping exhibitor backend
exhibitor_storage_backend: 'static'

# Upstream DNS resolvers for MesosDNS
resolvers:
- 8.8.8.8
- 8.8.4.4

# DCOS username and password
superuser_username:
superuser_password_hash:

ssh_user:
ssh_port: 22

process_timeout: 10000
bootstrap_url: 'file:///opt/dcos_install_tmp'
"""

        self.write_default_config = write_default_config
        self.defaults = yaml.load(defaults)
        self.config_path = config_path
        self.overrides = overrides
        self.build()
        self.errors = []

        log.debug("Configuration:")
        for k, v in self.items():
            log.debug("%s: %s", k, v)

    def _get_hidden_config(self):
        self.hidden_config = {
            'ip_detect_path':  IP_DETECT_PATH,
            'ssh_key_path': SSH_KEY_PATH,
            'ssh_key': self._try_loading_from_disk(SSH_KEY_PATH),
            'ip_detect_script': self._try_loading_from_disk(IP_DETECT_PATH)
        }

    def _try_loading_from_disk(self, path):
        if os.path.isfile(path):
            with open(path, 'r') as f:
                return f.read()
        else:
            return None

    def build(self):
        # Create defaults
        for key, value in self.defaults.items():
            self[key] = value
        # Get user config file configuration
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
            no_config_write = ['ssh_key', 'ip_detect_script']
            for key, value in self.overrides.items():
                if key == 'ssh_key':
                    self.write_to_disk(value, SSH_KEY_PATH, mode=0o600)
                elif key == 'ip_detect_script':
                    self.write_to_disk(value, IP_DETECT_PATH)
                elif key == 'rexray_config':
                    self['rexray_config_method'] = 'file'
                    self['rexray_config_filename'] = REXRAY_CONFIG_PATH
                    self.write_to_disk(value, REXRAY_CONFIG_PATH)

                if key in no_config_write:
                    pass
                elif key in arrays and value is None:
                    log.warning("Overriding %s: %s -> %s", key, self[key], value)
                    self[key] = list(value)
                else:
                    log.warning("Overriding %s: %s -> %s", key, self.get(key), value)
                    self[key] = value

    def validate(self):
        config = self._unbind_configuration()
        self._get_hidden_config()
        config.update(self.hidden_config)
        log.debug(config)
        _, messages = DCOSValidateConfig(config).validate()
        return messages

    def get_config(self):
        """
        Get config from disk.
        """
        if os.path.isfile(self.config_path):
            log.debug("Loading YAML configuration: %s", self.config_path)
            with open(self.config_path, 'r') as data:
                configuration = yaml.load(data)

        else:
            if self.write_default_config:
                log.error(
                    "Configuration file not found, %s. Writing new one with all defaults.",
                    self.config_path)
                self.write()
                configuration = yaml.load(open(self.config_path))
            else:
                log.error("Configuration file not found: %s", self.config_path)
                return {}

        return configuration

    def write(self):
        if self.config_path:
            data = open(self.config_path, 'w')
            data.write(yaml.dump(self._unbind_configuration(), default_flow_style=False, explicit_start=True))
            data.close()
        else:
            log.error("Must pass config_path=/path/to/file to execute .write().")

    def write_to_disk(self, data, path, mode=0o644):
        log.warning('Writing {} with mode {}: {}'.format(path, mode, data))
        if data is not None and data is not "":
            f = open(path, 'w')
            f.write(data)
            os.chmod(path, mode)
        else:
            log.warning('Request to write file {} ignored.'.format(path))
            log.warning('Cowardly refusing to write empty values or None data to disk.')

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

    def make_gen_config(self):
        gen_config = {}
        for key, value in self.items():
            # Remove config values that don't concern gen
            if key in [
                    'log_directory',
                    'ssh_user',
                    'ssh_port',
                    'ssh_key',
                    'ssh_key_path',
                    'agent_list',
                    'ip_detect_path',
                    'ip_detect_script',
                    'process_timeout',
                    'rexray_config']:
                continue
            log.debug('Adding {}: {} to gen.generate() configuration'.format(key, value))
            # stringify the keys as they're added in:
            if isinstance(value, list):
                log.debug("Caught list for genconf configuration, transforming to JSON string: %s", list)
                value = json.dumps(value)
            gen_config[key] = value

        log.debug('Complete genconf configuration: \n{}'.format(gen_config))
        return gen_config
