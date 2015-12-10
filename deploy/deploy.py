import glob
import logging

from deploy.util import create_agent_list, create_full_inventory, get_runner
from ssh.utils import handle_command
from ssh.validate import ExecuteException

log = logging.getLogger(__name__)


def copy_dcos_install(deploy, local_install_path=None, remote_install_path=None):
    if local_install_path is None:
        local_install_path = '/genconf/serve/dcos_install.sh'

    if remote_install_path is None:
        remote_install_path = '/tmp/'
    log.debug('copy dcons_install.sh: local {} to remote {}'.format(local_install_path, remote_install_path))
    handle_command(lambda: deploy.copy_cmd(local_install_path, remote_install_path))


def copy_packages(deploy, local_pkg_path=None, remote_pkg_path=None):
    if local_pkg_path is None:
        local_pkg_path = '/genconf/serve/packages/'

    if remote_pkg_path is None:
        remote_pkg_path = '/tmp'
    log.debug('copy packages: local {} to remote {}'.format(local_pkg_path, remote_pkg_path))
    handle_command(lambda: deploy.copy_cmd(local_pkg_path, remote_pkg_path, recursive=True))


def copy_bootstrap(deploy, local_bs_path, remote_bs_path=None):
    if remote_bs_path is None:
        remote_bs_path = '/tmp/bootstrap/'

    log.debug('create dir on remote hosts: {}'.format(remote_bs_path))
    handle_command(lambda: deploy.execute_cmd('mkdir -p {}'.format(remote_bs_path)))

    log.debug('copy bootstrap tarball: local {} to remote {}'.format(local_bs_path, remote_bs_path))
    handle_command(lambda: deploy.copy_cmd(local_bs_path, remote_bs_path))


def get_bootstrap_tarball():
    # TODO(mnaboka) pass explicit bootstrap id
    bootstrap_ls = glob.glob("/genconf/serve/bootstrap/*")
    if not bootstrap_ls:
        log.error("Ensure that the bootstrap tar ball exists in /genconf/serve/bootstrap")
        log.error("You must run genconf.py before attempting Deploy.")
        raise ExecuteException('bootstrap tarball not found /genconf/serve/bootstrap')
    return bootstrap_ls[0]


def deploy_masters(config):
    master_deploy = get_runner(config, config['cluster_config']['master_list'])
    log.debug('execute sudo bash /tmp/dcos_install.sh master')
    handle_command(lambda: master_deploy.execute_cmd('sudo bash /tmp/dcos_install.sh master'))


def deploy_agents(config):
    agent_list = create_agent_list(config['cluster_config']['master_list'], config['ssh_config']['target_hosts'])
    if not agent_list:
        log.warning('No agents found to deploy, check config.yaml')
        return
    agent_deploy = get_runner(config, agent_list)
    log.debug('execute sudo bash /tmp/dcos_install.sh slave')
    handle_command(lambda: agent_deploy.execute_cmd('sudo bash /tmp/dcos_install.sh slave'))


def install_dcos(config):
    """
    Copies the bootstrap tarball, install script, and executes the install process on
    masters and agents in the DCOS cluster
    """
    log.info("Installing DCOS")
    # Install script variables
    bootstrap_tarball = get_bootstrap_tarball()

    log.debug("Local bootstrap found: %s", bootstrap_tarball)

    all_targets = create_full_inventory(config['cluster_config']['master_list'], config['ssh_config']['target_hosts'])

    # Deploy the file to all targets
    deploy = get_runner(config, all_targets)

    # Copy dcos-install.sh
    copy_dcos_install(deploy)

    # Copy packages to all targets
    copy_packages(deploy)

    # Copy bootstrap tarball
    copy_bootstrap(deploy, bootstrap_tarball)

    # Deploy masters
    deploy_masters(config)

    # Deploy agents
    deploy_agents(config)
