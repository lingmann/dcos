# Configuration loader for dcosgen
# Set all configuration for a given run with a simple map
# my_opts = {
#     'config_dir':  '/tmp'
# }
#
# c = DcosConfigObject().set(my_opts)
# print(c)

import datetime
import time
import json
import os
import sys
import yaml

from dcosgen.validate import DCOSValidateConfig
from dcosgen import DCOSLogger
log = DCOSLogger(__name__).log


class DCOSConfig(dict):
    """
    Return the site configuration object for dcosgen library
    """
    def __init__(self, options={}):
        # Default configuration
        self.defaults = {
            'available_install_types': ['onprem'],
            'cluster_name': str(datetime.datetime.now()),
            'install_type': 'onprem',
            'config_dir': '{}/dcos-installer'.format(os.path.expanduser('~')),
            "num_masters": 3,
            "master_discovery": 'static',
            "master_list": ['127.0.0.1'],
            "exhibitor_storage_backend": "zookeeper",
            "exhibitor_zk_hosts": ['127.0.0.1'],
            "exhibitor_zk_path": '/exhibitor',
            "weights": "slave_public=1",
            "bootstrap_url": "localhost",
            "roles": "slave_public",
            "docker_remove_delay": "1hrs",
            "gc_delay": "2days",
            'resolvers': ['8.8.8.8', '8.8.4.4'],
        }   

        # Setting the passed in options as the overrides for the instance of the class. 
        self.overrides = options
        self._update()

        # Ensure our install_type is available
        if not self['install_type'] in self['available_install_types']:
            raise ValueError('Install type {} not available. Available types: {}'.format(self['install_type'], ['self.available_install_types']))

        # Ensure the path to the config file is present, and if not set a sane default
        if not 'user_config_path' in self:
            user_config_path = '{}/dcos_config.yaml'.format(self['config_dir'])
            log.warn("Using default configuration file path since 'user_config_path' was not passed: %s", user_config_path)
            self['user_config_path'] = user_config_path

        # Get user config file configuration
        user_config = self.load_user_config(self['user_config_path'])
        print(user_config)
        # Add user-land configuration
        if len(user_config) > 0:
            for k, v in user_config.items():
                self[k] = v
            
        else: 
            log.warn("No user configuration passed, using all defaults.") 

        log.debug("Configuration:")
        for k, v in self.items():
            log.debug("%s: %s", k, v)

        self._validate()


    def _update(self):
        # Create defaults
        for key, value in self.defaults.items():
            self[key] = value

        # Add user config if any
        if len(self.overrides) > 0:
            for key, value in self.overrides.items():
                self[key] = value


    def _validate(self):
        # Convienience function to validate this object
        DCOSValidateConfig(self)

    
    def load_user_config(self, config_path):
        """
        Load user-land configuration and exit upon errors.
        """
        log.debug("Trying to load %s", config_path)
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
                sys.exit(1)

        else:
            log.error("Configuration file not found, %s", config_path)
            log.warn("Using ALL DEFAULT configuration since %s was not found.", config_path)
            data = open(config_path, 'w') 
            data.write(yaml.dump(self.defaults, default_flow_style=False, explicit_start=True))
            data.close()
            return yaml.load(open(config_path, 'r'))
