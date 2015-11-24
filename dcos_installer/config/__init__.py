# Configuration loader for dcosgen
# Set all configuration for a given run with a simple map
# my_opts = {
#     'config_dir':  '/tmp'
# }
#
# c = DcosConfig()
# print(c)

import datetime
import time
import json
import os
import sys
import yaml

from dcos_installer.validate import DCOSValidateConfig
from dcos_installer.log import DCOSLog
log = DCOSLog(__name__).log


class DCOSConfig(dict):
    """
    Return the site configuration object for dcosgen library
    """
    def __init__(self, overrides={}, config_path=None):
        # Default configuration
        self.defaults = {
            'cluster_name': 'Mesosphere: The Data Center Operating System', #'New Cluster {}'.format(str(datetime.datetime.now())),
            'config_dir': '{}/dcos-installer'.format(os.path.expanduser('~')),
            'ip_detect_path': '{}/dcos-installer/ip-detect'.format(os.path.expanduser('~')),
            "num_masters": 3,
            "master_discovery": 'static',
            "master_list": ['127.0.0.1'],
            "agent_list": ["127.0.0.1"],
            "exhibitor_storage_backend": "zookeeper",
            "exhibitor_zk_hosts": ['127.0.0.1'],
            "exhibitor_zk_path": '/exhibitor',
            "weights": "slave_public=1",
            "bootstrap_url": "localhost",
            "roles": "slave_public",
            "docker_remove_delay": "1hrs",
            "gc_delay": "2days",
            'resolvers': ['8.8.8.8', '8.8.4.4'],
            'ssh_user': None, 
            'ssh_port': 22,
            'ssh_key_path': '{}/dcos-installer/ssh_key'.format(os.path.expanduser('~')),
        }   

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
                log.warn("No user configuration found, using all defaults.") 

        # Add user config if any
        if len(self.overrides) > 0:
            for key, value in self.overrides.items():
                self[key] = value


    def validate(self):
        # Convienience function to validate this object
        DCOSValidateConfig(self)

    
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
            data = open(config_path, 'w') 
            data.write(yaml.dump(self.defaults, default_flow_style=False, explicit_start=True))
            data.close()
            return yaml.load(open(config_path, 'r'))
