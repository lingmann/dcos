import argparse
import asyncio
import logging
import sys

from dcos_installer import action_lib
from dcos_installer import async_server, backend
from ssh.utils import AbstractSSHLibDelegate

import coloredlogs

log = logging.getLogger(__name__)

LOG_FORMAT = '%(asctime)-15s %(module)s %(message)s'


class CliDelegate(AbstractSSHLibDelegate):
    def on_update(self, future, callback_called):
        chain_name, result_object, host = future.result()
        callback_called.set_result(True)

    def on_done(self, name, result, host_object, host_status_count=None, host_status=None):
        print('Running {}'.format(name))
        for host, output in result.items():
            print('#' * 20)
            if output['returncode'] != 0:
                print(host)
                print('STDOUT')
                print('{}: {}'.format(host, '\n'.join(output['stdout'])))
                print('STDERR')
                print('{}: {}'.format(host, '\n'.join(output['stderr'])))


def run_loop(action, options):
    assert callable(action)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    log.debug('### START {}'.format(action.__name__))
    try:
        config = backend.get_config()
        cli_delegate = CliDelegate()
        result = loop.run_until_complete(action(config, block=True, async_delegate=cli_delegate))
    finally:
        loop.close()
    exitcode = 0
    for host_result in result:
        for command_result in host_result:
            for host, process_result in command_result.items():
                if process_result['returncode'] != 0:
                    exitcode = process_result['returncode']
    log.debug('### END {} with returncode: {}'.format(action.__name__, exitcode))
    print('check logfile {}'.format(options.log_file))
    if exitcode == 0:
        print('Success')
    else:
        print('Failed')
    return exitcode


class DcosInstaller:
    def __init__(self, args=None):
        """
        The web based installer leverages Flask to present end-users of
        dcos_installer with a clean web interface to configure their
        site-based installation of DCOS.
        """
        # If no args are passed to the class, then we're calling this
        # class from another library or code so we shouldn't execute
        # parser or anything else
        if args:
            options = self.parse_args(args)

            if options.web:
                log.warning("Starting DCOS installer in web mode")
                async_server.start(options.port)

            if options.configure:
                log.warning("Executing configuration generation for DCOS.")
                backend.do_configure()

            if options.preflight:
                log.warning("Executing preflight on target hosts.")
                sys.exit(run_loop(action_lib.run_preflight, options))

            if options.deploy:
                log.warning("Executing deploy on target hosts.")
                for role in ['master', 'agent']:
                    deploy_returncode = run_loop(lambda *args, **kwargs: action_lib.install_dcos(*args, role=role,
                                                                                                 **kwargs), options)
                if deploy_returncode != 0:
                    sys.exit(deploy_returncode)
                sys.exit(0)

            if options.postflight:
                log.warning("Executing postflight on target hosts.")
                sys.exit(run_loop(action_lib.run_postflight, options))

            if options.uninstall:
                log.warning("Executing uninstall on target hosts.")
                sys.exit(run_loop(action_lib.uninstall_dcos, options))

    def parse_args(self, args):
        """
        Parse CLI arguments and return a map of options.
        """
        parser = argparse.ArgumentParser(description='Install DCOS on-premise')
        mutual_exc = parser.add_mutually_exclusive_group()

        # Log level
        parser.add_argument(
            '-f',
            '--log-file',
            default='/genconf/logs/installer.log',
            type=str,
            help='Set log file location, default: /genconf/logs/installer.log'
        )

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
            '-u',
            '--uninstall',
            action='store_true',
            default=False,
            help='Execute uninstall on target hosts.')

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
        level = 'INFO'
        if options.verbose:
            level = 'DEBUG'

        coloredlogs.install(
            level=level,
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
            fmt='%(asctime)s %(name)s:: %(message)s'
        )

        log.debug("Logger set to DEBUG")

        return options
