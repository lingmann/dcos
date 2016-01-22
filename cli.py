import argparse
import asyncio
import logging as log
import sys

import action_lib
from dcos_installer import backend
from ssh.utils import AbstractSSHLibDelegate

LOG_FORMAT = '%(asctime)-15s %(module)s %(message)s'


class CliDelegate(AbstractSSHLibDelegate):
    def on_update(self, future, callback_called):
        chain_name, result_object = future.result()
        callback_called.set_result(True)

    def on_done(self, name, result, host_status_count=None, host_status=None):
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


def main():
    parser = argparse.ArgumentParser(description="Generates DCOS configuration.")
    ssh_deployer = parser.add_mutually_exclusive_group()

    # Log level
    parser.add_argument(
        '-f',
        '--log-file',
        default='/genconf/logs/installer.log',
        type=str,
        help='Set log file location'
    )

    parser.add_argument(
        '-l',
        '--log-level',
        default='debug',
        type=str,
        choices=['debug', 'info'],
        help='Log level. Info or debug')

    # Set preflight flag
    ssh_deployer.add_argument(
        '--preflight',
        action='store_true',
        help='Execute preflight on target DCOS hosts.')

    # Set deploy flag
    ssh_deployer.add_argument(
        '--deploy',
        action='store_true',
        help='Install DCOS on target DCOS hosts.')

    # Set postflight flag
    ssh_deployer.add_argument(
        '--postflight',
        action='store_true',
        help='Execute the post-flight on target DCOS hosts.')

    # Clean flag
    ssh_deployer.add_argument(
        '--uninstall',
        action='store_true',
        help='Uninstall DCOS on target DCOS hosts.')

    # Parse the arguments and dispatch.
    options = parser.parse_args()
    log_level = {
        'info': log.INFO,
        'debug': log.DEBUG
    }

    if options.log_level:
        log.basicConfig(filename=options.log_file, level=log_level.get(options.log_level), format=LOG_FORMAT)
    #    log.debug("Log level set to {}".format(options.log_level))

    if options.preflight:
        sys.exit(run_loop(action_lib.run_preflight, options))

    if options.deploy:
        for role in ['master', 'agent']:
            deploy_returncode = run_loop(lambda *args, **kwargs: action_lib.install_dcos(*args, role=role, **kwargs),
                                         options)
            if deploy_returncode != 0:
                sys.exit(deploy_returncode)
        sys.exit(0)

    if options.postflight:
        sys.exit(run_loop(action_lib.run_postflight, options))

    if options.uninstall:
        sys.exit(run_loop(action_lib.uninstall_dcos, options))

    parser.print_help()

if __name__ == '__main__':
    main()