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
log = logging.getLogger()


class DCOSConfig(dict):
    """
    Return the site configuration object for dcosgen library
    """
    def __init__(self, overrides={}, config_path=None, post_data={}):
        defaults = """
---
cluster_config:
  # The name of your DCOS cluster. Visable in the DCOS user interface.
  cluster_name: 'Mesosphere: The Data Center Operating System'

  # The IPv4 addresses of your master hosts
  master_list:
  -

  # The bootstrapping exhibitor hosts. Format is ip:port.
  exhibitor_zk_hosts: 127.0.0.1:2181

  # Upstream DNS resolvers for MesosDNS
  resolvers:
    -

# SSH configuration for --deploy, --preflight, --uninstall, --postflight
ssh_config:
  # The IPv4 addresses of your target hosts
  target_hosts:
  -
  ssh_key_path: /genconf/ssh_key
  ssh_user:
  ssh_port: 22
  process_timeout: 120

  # Optional parameter for executing SSH with an attached TTY. Useful in
  # AWS or other environments which require a tty with your ssh session
  # to execute sudo on remote machines.
  # extra_ssh_options: -tt
"""
        # TODO set this to validate()? What does validate return? messages,config?
        self.defaults = yaml.load(defaults)
        self.post_data = post_data
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

        # Update with data from POST
        self._add_post_data()

        # Ensure target list is defined properly
        self._create_full_inventory()

    def _create_full_inventory(self):
        '''
        Join 2 lists of masters and all hosts to make sure we are addressing all available hosts.
        :config Dict, /genconf/config.yaml object
        :return: joined unique list of masters and all targets
        '''
        self['ssh_config']['target_hosts'] = list(set(self['cluster_config']['master_list']) |
                                                  set(self['ssh_config']['target_hosts']))

    def _add_overrides(self):
        """
        Add overrides. Overrides expects data in the same format as the config file.
        """
        arrays = ['master_list', 'resolvers', 'target_hosts']
        if self.overrides is not None and len(self.overrides) > 0:
            for key, value in self.overrides.items():
                if isinstance(value, dict):
                    for k1, v1 in value.items():
                        log.warning("Overriding %s with %s", self[key][k1], v1)
                        if k1 in arrays and v1 is None:
                            self[key][k1] = list(v1)
                        else:
                            self[key][k1] = v1

    def _add_post_data(self):
        """
        Ingests the data from a POST from the UI and conforms it to our
        config file standard.
        """
        if 'master_ips' in self.post_data and self.post_data['master_ips'] is not None:
            log.debug("Master IPs found in POST data, adding to config.")
            self['cluster_config']['master_list'] = self.post_data['master_ips']

        if 'agent_ips' in self.post_data and self.post_data['agent_ips'] is not None:
            log.debug("Agent IPs found in POST data, adding to config.")
            self['ssh_config']['target_hosts'] = self.post_data['agent_ips']

        if 'ssh_username' in self.post_data:
            self['ssh_config']['ssh_user'] = self.post_data['ssh_username']

        if 'ssh_port' in self.post_data:
            self['ssh_config']['ssh_port'] = self.post_data['ssh_port']

        if 'upstream_dns_servers' in self.post_data:
            self['cluster_config']['resolvers'] = self.post_data['upstream_dns_servers']

    def validate(self):
        # TODO Leverage Gen library from here
        # Convienience function to validate this object
        _, messages = DCOSValidateConfig(self).validate()
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
