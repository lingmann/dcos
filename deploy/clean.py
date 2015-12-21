import logging

from deploy.console_printer import clean_logs, print_failures, print_header
from deploy.util import create_full_inventory, deploy_handler, get_runner

log = logging.getLogger(__name__)


def execute_uninstall(runner):
    """
    Copies the bootstrap tarball, install script, and executes the install process on
    masters and agents in the DCOS cluster
    """
    # Execute install on agents
    print_header('UNINSTALLING DCOS FROM TARGET HOSTS')
    deploy_handler(
        lambda: runner.execute_cmd('sudo -i /opt/mesosphere/bin/pkgpanda uninstall && sudo rm -rf /opt/mesosphere/'))


def uninstall_dcos(config):
    """
    Uninstall DCOS from target hosts.
    """
    clean_logs('uninstall', config['ssh_config']['log_directory'])
    print_header("Uninstalling DCOS")
    all_targets = create_full_inventory(config)

    # clean the file to all targets
    runner = get_runner(config, all_targets, 'uninstall')
    try:
        execute_uninstall(runner)
    finally:
        print_failures('uninstall', config['ssh_config']['log_directory'])
