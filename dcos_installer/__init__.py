import argparse
import logging as log
import sys
import os
from . import server
from . import preflight
from . import deploy

class DcosInstaller:
    def __init__(self):
        """
        The web based installer leverages Flask to present end-users of 
        dcos_installer with a clean web interface to configure their
        site-based installation of DCOS.
        """
        options = self.parse_args()
        self.set_log_level(options)
        self.set_install_dir(options)
        if options.mode == 'web':
            server.run(options)
        else:
            log.error("Sorry, %s is not a usable run mode.", options.mode)
            sys.exit(1)

    def parse_args(self):
        """
        Parse CLI arguments and return a map of options.
        """
        # Get the user's homedir in a cross platfrom manner
        homedir    = os.path.expanduser('~')
        installdir = '{}/dcos-installer'.format(homedir)

        parser = argparse.ArgumentParser(description='Install DCOS on-premise')
        parser.add_argument(
            '-p', 
            '--port',
            type=int,
            default=9000,
            help='Web server port number.')

        parser.add_argument(
            '-l',
            '--log-level',
            type=str,
            default='info',
            choices=['info','debug'],
            help='Log level.')

        parser.add_argument(
            '-m',
            '--mode',
            type=str,
            choices=['non-interactive', 'interactive', 'web'],
            default='web',
            help='Installation mode.')

        parser.add_argument(
            '-c',
            '--config-path',
            type=str,
            default='{}/dcos_config.yaml'.format(installdir),
            help='The path to dcos_config.yaml.')

        parser.add_argument(
            '-d',
            '--install-directory',
            type=str,
            default=installdir,
            help='The install directory for the DCOS installer.')

        options = parser.parse_args()
        return options

    
    def set_install_dir(self, options):
        """
        Ensures the default or user provided install directory path
        exists.
        """
        try:
            os.stat(options.install_directory)
        except:
            log.info('{} does not exist, creating.'.format(options.install_directory))
            os.mkdir(options.install_directory)       


    def set_log_level(self,options):
        """
        Given a map of options, parse for log level flag and set the 
        default logging level.
        """
        if options.log_level == "debug":
            log.basicConfig(level=log.DEBUG)
            log.debug("Log level set to DEBUG")
        elif options.log_level == "info":
            log.basicConfig(level=log.INFO)
            log.info("Log level set to INFO")
        else:
            log.error("Logging option not available: %s", options.log_level)
            sys.exit(1)

