import argparse
import logging as log
import sys
import os
from . import server
#from . import cli

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
        # Can set top level install dir as env var or accept default in $HOME
        homedir    = os.path.expanduser('~')
        if 'DCOS_INSTALL_DIR' in os.environ:
            installdir = os.environ['DCOS_INSTALL_DIR']
        else:
            installdir = '{}/dcos-installer'.format(homedir)
        
        parser = argparse.ArgumentParser(description='Install DCOS on-premise')
        parser.add_argument(
            '--preflight-results-path',
            type=str,
            default='{}/preflight-results.log'.format(installdir),
            help='Path to the preflight-results.log.')

        parser.add_argument(
            '--dcos-install-script-path',
            type=str,
            default='install_dcos.sh',
            help='The path to install_dcos.sh script. Defaults to sibling of the project repo.')

        parser.add_argument(
            '--ssh-key-path',
            type=str,
            default='{}/ssh_key'.format(installdir),
            help='The path to the private ssh key for preflight and deploy functionality.')

        parser.add_argument(
            '--hosts-yaml-path',
            type=str,
            default='{}/hosts.yaml'.format(installdir),
            help='The path to the hosts.yaml for preflight and deploy functionlity.')

        parser.add_argument(
            '--ssh-user-path',
            type=str,
            default='{}/ssh_user'.format(installdir),
            help='The path to ssh_user file containing the name of the user for SSH access. Required for preflight and deploy functionality.')

        parser.add_argument(
            '--ip-detect-path',
            type=str,
            default='{}/ip-detect'.format(installdir),
            help='The path to the ip-detect script.')

        parser.add_argument(
            '-c',
            '--config-path',
            type=str,
            default='{}/dcos_config.yaml'.format(installdir),
            help='The path to dcos_config.yaml.')

        # TODO - implement CLI utility
        parser.add_argument(
            '-d',
            '--deploy',
            action='store_true',
            default=False,
            help='Execute a deploy. Assumes preflight checks have already been executed and the cluster is in a usable state.')

        parser.add_argument(
            '-i',
            '--install-directory',
            type=str,
            default=installdir,
            help='The install directory for the DCOS installer.')

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
            '-p', 
            '--port',
            type=int,
            default=9000,
            help='Web server port number.')

        parser.add_argument(
            '--serve-directory',
            type=str,
            default='{}/serve'.format(installdir),
            help='The path to the serve directory. Used to dump generated config and packages.')

        # TODO - implement CLI utility
        parser.add_argument(
            '-pre',
            '--preflight',
            action='store_true',
            default=False,
            help='Execute the preflight checks on a series of nodes. Assumes $INSTALL_DIR/hosts.yaml exists.')

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

