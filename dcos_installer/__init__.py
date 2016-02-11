import argparse
import asyncio
import logging
import os
import sys

from dcos_installer import action_lib, backend
from dcos_installer.action_lib.prettyprint import print_header, PrettyPrint
from dcos_installer import async_server
from dcos_installer.util import GENCONF_DIR
from ssh.utils import AbstractSSHLibDelegate

import coloredlogs

log = logging.getLogger(__name__)

LOG_FORMAT = '%(asctime)-15s %(module)s %(message)s'


class CliDelegate(AbstractSSHLibDelegate):
    def on_update(self, future, callback_called):
        chain_name, result_object, host = future.result()
        callback_called.set_result(True)
        log.debug('on_update executed for {}'.format(chain_name))

    def on_done(self, name, result, host_object, host_status=None):
        print_header('STAGE {}'.format(name))


def run_loop(action, options):
    assert callable(action)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    print_header('START {}'.format(action.__name__))
    try:
        config = backend.get_config()
        cli_delegate = CliDelegate()
        result = loop.run_until_complete(action(config, block=True, async_delegate=cli_delegate, options=options))
        pp = PrettyPrint(result)
        pp.stage_name = action.__name__
        pp.beautify('print_data')

    finally:
        loop.close()
    exitcode = 0
    for host_result in result:
        for command_result in host_result:
            for host, process_result in command_result.items():
                if process_result['returncode'] != 0:
                    exitcode = process_result['returncode']
    print_header('END {} with returncode: {}'.format(action.__name__, exitcode))
    pp.print_summary()
    return exitcode


def make_default_dir(dir=GENCONF_DIR):
    """
    So users do not have to set the directories in the config.yaml,
    we build them using sane defaults here first.
    """
    if not os.path.exists(dir):
        log.info('Creating {}'.format(dir))
        os.makedirs(dir)


def check_config_validation(gen_val=False):
    '''Gen validation needs to ignore all warnings (optional) validation which
    includes SSH stuff. However, if we do have warnings, we need to ensure this
    validation passes even if superuser_username and superuser_password_hash
    exist since they're optional between CE and EE'''
    messages, code = backend.do_validate_config()
    if code == 1:
        if gen_val:
            log.error("Configuration generation (--genconf) requires the following errors to be fixed:")
            keys = messages['errors'].keys()
            for key in keys:
                log.error(key)

        sys.exit(1)

    elif code == 2 and not gen_val:
        dual_distro = ['superuser_username', 'superuser_password_hash']
        warn = messages.get('warning')
        for k in dual_distro:
            if k in warn:
                del warn[k]
        if len(warn) > 0:
            log.error("Please fix all warnings and errors before proceeding.")
            sys.exit(1)


def try_genconf():
    check_config_validation(gen_val=True)
    messages = backend.do_configure()
    if 'errors' in messages:
        for k, v in messages['errors'].items():
            log.error('{}: {}'.format(k, v))
        log.error('Errors found in configuration.')
        sys.exit(1)
    sys.exit(0)


def tall_enough_to_ride():
    choices_true = ['Yes', 'yes', 'y']
    choices_false = ['No', 'no', 'n']
    while True:
        do_uninstall = input(
'This will uninstall DCOS on your cluster. You may need to manually remove /var/lib/zookeeper in some cases after this completes, please see our documentation for details. Are you ABSOLUTELY sure you want to proceed? [ (y)es/(n)o ]: ')  # noqa
        if do_uninstall in choices_true:
            return True
        elif do_uninstall in choices_false:
            return False
        else:
            log.error('Choices are [y]es or [n]o. "{}" is not a choice'.format(do_uninstall))


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
            if len(options.hash_password) > 0:
                print_header("HASHING PASSWORD TO SHA512")
                backend.hash_password(options.hash_password)
                sys.exit(0)

            if options.web:
                make_default_dir()
                print_header("Starting DCOS installer in web mode")
                async_server.start(options)

            if options.genconf:
                make_default_dir()
                print_header("EXECUTING CONFIGURATION GENERATION")
                try_genconf()

            if options.preflight:
                print_header("EXECUTING PREFLIGHT")
                check_config_validation()
                sys.exit(run_loop(action_lib.run_preflight, options))

            if options.deploy:
                print_header("EXECUTING DCOS INSTALLATION")
                check_config_validation()
                deploy_returncode = 0
                for role in ['master', 'agent']:
                    action = lambda *args, **kwargs: action_lib.install_dcos(*args, role=role, **kwargs)
                    action.__name__ = 'deploy_{}'.format(role)
                    stage_returncode = run_loop(action, options)
                    if stage_returncode != 0:
                        deploy_returncode = 1
                sys.exit(deploy_returncode)

            if options.postflight:
                check_config_validation()
                print_header("EXECUTING POSTFLIGHT")
                sys.exit(run_loop(action_lib.run_postflight, options))

            if options.uninstall:
                check_config_validation()
                if tall_enough_to_ride():
                    print_header("EXECUTING UNINSTALL")
                    sys.exit(run_loop(action_lib.uninstall_dcos, options))
                # Not sure if we need to exit 1 or 0 here TODO
                sys.exit(0)

            if options.validate_config:
                make_default_dir()
                print_header('VALIDATING CONFIGURATION')
                check_config_validation()

            if options.install_prereqs:
                print_header("EXECUTING INSTALL PREREQUISITES")
                check_config_validation()
                sys.exit(run_loop(action_lib.install_prereqs, options))

    def parse_args(self, args):
        def print_usage():
            return """
Install Mesosophere's Data Center Operating System

dcos_installer [-h] [-f LOG_FILE] [--hash-password HASH_PASSWORD] [-v]
[--web | --genconf | --preflight | --deploy | --postflight | --uninstall | --validate-config | --test]

Environment Settings:

  PORT                  Set the :port to run the web UI
  CHANNEL_NAME          ADVANCED - Set build channel name
  BOOTSTRAP_ID          ADVANCED - Set bootstrap ID for build

"""

        """
        Parse CLI arguments and return a map of options.
        """
        parser = argparse.ArgumentParser(usage=print_usage())
        mutual_exc = parser.add_mutually_exclusive_group()

        parser.add_argument(
            '--hash-password',
            default='',
            type=str,
            help='Hash a password on the CLI for use in the config.yaml.'
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
            help=argparse.SUPPRESS)

        parser.add_argument(
            '--offline',
            action='store_true',
            default=False,
            help='Do not install preflight prerequisites on CentOS7, RHEL7 in web mode'
        )

        mutual_exc.add_argument(
            '--web',
            action='store_true',
            default=False,
            help='Run the web interface.')

        mutual_exc.add_argument(
            '--genconf',
            action='store_true',
            default=False,
            help='Execute the configuration generation (genconf).')

        mutual_exc.add_argument(
            '--preflight',
            action='store_true',
            default=False,
            help='Execute the preflight checks on a series of nodes.')

        mutual_exc.add_argument(
            '--install-prereqs',
            action='store_true',
            default=False,
            help='Install preflight prerequisites. Works only on CentOS7 and RHEL7.')

        mutual_exc.add_argument(
            '--deploy',
            action='store_true',
            default=False,
            help='Execute a deploy.')

        mutual_exc.add_argument(
            '--postflight',
            action='store_true',
            default=False,
            help='Execute postflight checks on a series of nodes.')

        mutual_exc.add_argument(
            '--uninstall',
            action='store_true',
            default=False,
            help='Execute uninstall on target hosts.')

        mutual_exc.add_argument(
            '--validate-config',
            action='store_true',
            default=False,
            help='Validate the configuration in config.yaml')

        mutual_exc.add_argument(
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
            fmt='%(asctime)s %(name)s:: %(message)s',
            isatty=True
        )

        log.debug("Logger set to DEBUG")

        return options
