import argparse
import logging
import sys

from dcos_installer import server, pretty_log

# Get logger
log = logging.getLogger(__name__)


class DcosInstaller:
    def __init__(self, options=None):
        """
        The web based installer leverages Flask to present end-users of
        dcos_installer with a clean web interface to configure their
        site-based installation of DCOS.
        """
        if not options:
            options = self.parse_args(sys.argv[1:])
        self.set_log_level(options)

        if options.web:
            server.start(options)

    def set_log_level(self, options):
        """
        Given a map of options, parse for log level flag and set the
        default logging level.
        """
        if options.verbose:
            log.setLevel(logging.DEBUG)
            log.debug("Running with verbose logger")

    def parse_args(self, args):
        """
        Parse CLI arguments and return a map of options.
        """
        parser = argparse.ArgumentParser(description='Install DCOS on-premise')
        mutual_exc = parser.add_mutually_exclusive_group()

        parser.add_argument(
            '-v',
            '--verbose',
            action='store_true',
            default=False,
            help='Verbose log output (DEBUG).')

        parser.add_argument(
            '-p',
            '--port',
            type=int,
            default=9000,
            help='Web server port number.')

        mutual_exc.add_argument(
            '-w',
            '--web',
            action='store_true',
            default=False,
            help='Run the web interface.')

        mutual_exc.add_argument(
            '-c',
            '--configure',
            action='store_true',
            default=False,
            help='Execute the configuration generation (genconf).')

        mutual_exc.add_argument(
            '-pre',
            '--preflight',
            action='store_true',
            default=False,
            help='Execute the preflight checks on a series of nodes.')

        mutual_exc.add_argument(
            '-d',
            '--deploy',
            action='store_true',
            default=False,
            help='Execute a deploy.')

        mutual_exc.add_argument(
            '-pos',
            '--postflight',
            action='store_true',
            default=False,
            help='Execute postflight checks on a series of nodes.')

        mutual_exc.add_argument(
            '-vc',
            '--validate-config',
            action='store_true',
            default=False,
            help='Validate the configuration in config.yaml')

        mutual_exc.add_argument(
            '-t',
            '--test',
            action='store_true',
            default=False,
            help='Performs tests on the dcos_installer application')

        """
        The following arguments are suppressed. We are adding them
        because the genconf provider, specifically the do_genconf
        method requires these to exist in the parser object we pass
        to it. We do not want to exppose these to the end user and
        may remove them from the genconf provider at a later date.
        """
        parser.add_argument(
            '-l',
            '--log-level',
            default='info',
            type=str,
            choices=['debug', 'info'],
            help=argparse.SUPPRESS)

        parser.add_argument(
            '-o',
            '--output-dir',
            default='/genconf/serve',
            type=str,
            help=argparse.SUPPRESS)

        parser.add_argument(
            '-i',
            '--interactive',
            action='store_true',
            default=False,
            help=argparse.SUPPRESS)

        options = parser.parse_args(args)

        return options
