import argparse
import logging as log
import sys

from dcos_installer import async_server

import coloredlogs

coloredlogs.install(
    datefmt='%H:%M:%S',
    level_styles={
        'warn': {
            'color': 'yellow'
        },
        'error': {
            'color': 'red',
            'bold': True,
        },
    },
    field_styles={
        'asctime': {
            'color': 'blue'
        }
    },
    fmt='%(asctime)s :: %(message)s'
)


class DcosInstaller:
    def __init__(self):
        """
        The web based installer leverages Flask to present end-users of
        dcos_installer with a clean web interface to configure their
        site-based installation of DCOS.
        """
        options = self.parse_args(sys.argv[1:])
        self.set_log_level(options)

        if options.web:
            log.warning("Starting DCOS installer in web mode")
            async_server.start(options.port)
            # This was for the gunicorn wrapper:
            # run_gunicorn(options)

    def set_log_level(self, options):
        """
        Given a map of options, parse for log level flag and set the
        default logging level.
        """
        if options.verbose:
            log.basicConfig(level=log.DEBUG)
            log.debug("Log level set to DEBUG")
        else:
            log.basicConfig(level=log.INFO)
            log.info("Log level set to INFO")

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

        options = parser.parse_args(args)
        return options
