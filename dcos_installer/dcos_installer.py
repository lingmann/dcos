import argparse
import os
import sys

from dcos_installer import server
from dcos_installer.log import DCOSLog

log = DCOSLog(__name__).log

# Get the current relative directory
project_path=os.path.dirname(os.path.realpath(__file__))


class DcosInstaller:
    def __init__(self, options=None):
        """
        The web based installer leverages Flask to present end-users of
        dcos_installer with a clean web interface to configure their
        site-based installation of DCOS.
        """
        if not options:
            options=self.parse_args(sys.argv[1:])
        self.set_log_level(options)
        self.set_install_dir(options)

        if options.mode == 'web':
            server.run(options)
        else:
            log.error("Sorry, %s is not a usable run mode.", options.mode)
            sys.exit(1)

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
        # Logging directory
        try:
            os.stat(options.log_directory)
        except:
            log.info('{} does not exist, creating.'.format(options.log_directory))
            os.mkdir(options.log_directory)
        # Serve directory
        try:
            os.stat(options.serve_directory)
        except:
            log.info('{} does not exist, creating.'.format(options.serve_directory))
            os.mkdir(options.serve_directory)


    def set_log_level(self, options):
        """
        Given a map of options, parse for log level flag and set the
        default logging level.
        """
        log.log_level = options.log_level

    def parse_args(self,args):
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
            '--log-directory',
            type=str,
            default='{}/logs'.format(installdir),
            help='Path to the logging directory. Used for preflight.log and deploy.log..')

        parser.add_argument(
            '--dcos-install-script-path',
            type=str,
            default='{}/dcos_installer/templates/install_dcos.sh'.format(project_path),
            help='The path to install_dcos.sh script. Defaults to sibling of the project repo.')

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
            choices=['cli', 'web'],
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

        parser.add_argument(
            '-pre',
            '--preflight',
            action='store_true',
            default=False,
            help='Execute the preflight checks on a series of nodes. Assumes $INSTALL_DIR/hosts.yaml exists.')

        parser.add_argument(
            '-t',
            '--test',
            action='store_true',
            default=False,
            help='Performs tests on the dcos_installer application')

        options = parser.parse_args(args)

        return options
