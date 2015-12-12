import logging
import os

import pkgpanda

from deploy.util import create_agent_list, create_full_inventory, get_runner
from ssh.utils import handle_command
from ssh.validate import ExecuteException

log = logging.getLogger(__name__)

REMOTE_TEMP_DIR = '/opt/dcos_install_tmp'
CLUSTER_PACKAGES_FILE = '/genconf/cluster_packages.json'


def copy_dcos_install(deploy, local_install_path='/genconf/serve'):
    '''
    Copy dcos_install.sh to remote hosts
    :param deploy: Instance of preconfigured ssh.ssh_runner.SSHRunner
    :param local_install_path: dcos_install.sh script location on a local host
    :param remote_install_path: destination location
    '''
    dcos_install_script = 'dcos_install.sh'
    local_install_path = os.path.join(local_install_path, dcos_install_script)
    remote_install_path = os.path.join(REMOTE_TEMP_DIR, dcos_install_script)

    log.debug('{} -> {}'.format(local_install_path, remote_install_path))
    handle_command(lambda: deploy.copy_cmd(local_install_path, remote_install_path))


def copy_packages(deploy, local_pkg_base_path='/genconf/serve'):
    '''
    Copy packages to remote hosts
    :param deploy: Instance of preconfigured ssh.ssh_runner.SSHRunner
    :param local_pkg_path: packages directory location on a local host
    :param remote_pkg_path: destination location
    '''
    if not os.path.isfile(CLUSTER_PACKAGES_FILE):
        err_msg = '{} not found'.format(CLUSTER_PACKAGES_FILE)
        log.error(err_msg)
        raise ExecuteException(err_msg)

    cluster_packages = pkgpanda.load_json(CLUSTER_PACKAGES_FILE)
    log.debug(cluster_packages)
    for package, params in cluster_packages.items():
        destination_package_dir = os.path.join(REMOTE_TEMP_DIR, 'packages', package)
        local_pkg_path = os.path.join(local_pkg_base_path, params['filename'])

        log.debug('mkdir -p {}'.format(destination_package_dir))
        handle_command(lambda: deploy.execute_cmd('mkdir -p {}'.format(destination_package_dir)))

        log.debug('{} -> {}'.format(local_pkg_path, destination_package_dir))
        handle_command(lambda: deploy.copy_cmd(local_pkg_path, destination_package_dir))


def copy_bootstrap(deploy, local_bs_path):
    '''
    Copy bootstrap tarball to remote hosts
    :param deploy: Instance of preconfigured ssh.ssh_runner.SSHRunner
    :param local_bs_path: bootstrap tarball location on a local host
    :param remote_bs_path: destination location
    :return:
    '''
    remote_bs_path = REMOTE_TEMP_DIR + '/bootstrap'
    log.debug('create dir on remote hosts: {}'.format(remote_bs_path))
    handle_command(lambda: deploy.execute_cmd('mkdir -p {}'.format(remote_bs_path)))

    log.debug('{} -> {}'.format(local_bs_path, remote_bs_path))
    handle_command(lambda: deploy.copy_cmd(local_bs_path, remote_bs_path))


def get_bootstrap_tarball(tarball_base_dir='/genconf/serve/bootstrap'):
    '''
    Get a bootstrap tarball from a local filesystem
    :return: String, location of a tarball
    '''
    if 'BOOTSTRAP_ID' not in os.environ:
        err_msg = 'BOOTSTRAP_ID must be set'
        log.error(err_msg)
        raise ExecuteException(err_msg)

    tarball = os.path.join(tarball_base_dir, '{}.bootstrap.tar.xz'.format(os.environ['BOOTSTRAP_ID']))
    if not os.path.isfile(tarball):
        log.error('Ensure environment variable BOOTSTRAP_ID is set correctly')
        log.error('Ensure that the bootstrap tarball exists in '
                  '/genconf/serve/bootstrap/[BOOTSTRAP_ID].bootstrap.tar.xz')
        log.error('You must run genconf.py before attempting Deploy.')
        raise ExecuteException('bootstrap tarball not found /genconf/serve/bootstrap')
    return tarball


def deploy_masters(config):
    '''
    Deploy DCOS on master hosts
    :param config: Dict, loaded config file from /genconf/config.yaml
    '''
    master_deploy = get_runner(config, config['cluster_config']['master_list'])
    log.debug('execute sudo bash {}/dcos_install.sh master'.format(REMOTE_TEMP_DIR))
    handle_command(lambda: master_deploy.execute_cmd('sudo bash {}/dcos_install.sh master'.format(REMOTE_TEMP_DIR)))


def deploy_agents(config):
    '''
    Deploy DCOS on agent hosts
    :param config: Dict, loaded config file from /genconf/config.yaml
                   agent hosts are implicitly calculated: all_hosts - master_hosts
    '''
    agent_list = create_agent_list(config['cluster_config']['master_list'], config['ssh_config']['target_hosts'])
    if not agent_list:
        log.warning('No agents found to deploy, check config.yaml')
        return
    agent_deploy = get_runner(config, agent_list)
    log.debug('execute sudo bash {}/dcos_install.sh slave'.format(REMOTE_TEMP_DIR))
    handle_command(lambda: agent_deploy.execute_cmd('sudo bash {}/dcos_install.sh slave'.format(REMOTE_TEMP_DIR)))


def init_tmp_dir(deploy):
    log.info('Creating temp directory {}'.format(REMOTE_TEMP_DIR))
    handle_command(lambda: deploy.execute_cmd('sudo mkdir -p {}'.format(REMOTE_TEMP_DIR)))
    handle_command(lambda: deploy.execute_cmd('sudo chown {} {}'.format(deploy.ssh_user, REMOTE_TEMP_DIR)))


def cleanup_tmp_dir(deploy):
    log.info('Cleaning up temp directory {}'.format(REMOTE_TEMP_DIR))
    handle_command(lambda: deploy.execute_cmd('sudo rm -rf {}'.format(REMOTE_TEMP_DIR)))


def install_dcos(config):
    '''
    Main function to deploy DCOS on master and agent hosts from config file.
    :param config: Dict, loaded config file from /genconf/config.yaml
    :raises: ssh.validate.ExecuteException if command execution fails
             ssh.validate.ValidationException if ssh config validation fails
    '''
    log.info("Installing DCOS")
    bootstrap_tarball = get_bootstrap_tarball()

    log.debug("Local bootstrap found: %s", bootstrap_tarball)

    all_targets = create_full_inventory(config['cluster_config']['master_list'], config['ssh_config']['target_hosts'])

    deploy = get_runner(config, all_targets)

    try:
        init_tmp_dir(deploy)
        copy_dcos_install(deploy)
        copy_packages(deploy)
        copy_bootstrap(deploy, bootstrap_tarball)
        deploy_masters(config)
        deploy_agents(config)
    finally:
        cleanup_tmp_dir(deploy)
