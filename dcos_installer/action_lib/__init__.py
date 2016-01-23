import asyncio
import logging
import os

import pkgpanda
from ssh.ssh_runner import Server
from ssh.exceptions import ExecuteException
import ssh.utils

from .utils import REMOTE_TEMP_DIR, CLUSTER_PACKAGES_FILE, get_async_runner, add_post_action, add_pre_action

log = logging.getLogger(__name__)


@asyncio.coroutine
def run_preflight(config, pf_script_path='/genconf/serve/dcos_install.sh', block=False, state_json_dir=None, **kwargs):
    '''
    Copies preflight.sh to target hosts and executes the script. Gathers
    stdout, sterr and return codes and logs them to disk via SSH library.
    :param config: Dict, loaded config file from /genconf/config.yaml
    :param pf_script_path: preflight.sh script location on a local host
    :param preflight_remote_path: destination location
    '''
    if not os.path.isfile(pf_script_path):
        log.error("genconf/serve/dcos_install.sh does not exist. Please run --genconf before executing preflight.")
        raise FileNotFoundError('genconf/serve/dcos_install.sh does not exist')
    targets = []
    for host in config['master_list']:
        s = Server(host)
        s.add_tag({'role': 'master'})
        targets += [s]

    for host in config['agent_list']:
        s = Server(host)
        s.add_tag({'role': 'agent'})
        targets += [s]

    pf = get_async_runner(config, targets, **kwargs)
    preflight_chain = ssh.utils.CommandChain('preflight')

    add_pre_action(preflight_chain, pf.ssh_user)
    preflight_chain.add_copy(pf_script_path, REMOTE_TEMP_DIR, comment='COPYING PREFLIGHT SCRIPT TO TARGETS')

    preflight_chain.add_execute(
        'sudo bash {} --preflight-only master'.format(
            os.path.join(REMOTE_TEMP_DIR, os.path.basename(pf_script_path))).split(),
        comment='EXECUTING PREFLIGHT CHECK ON TARGETS')
    add_post_action(preflight_chain)

    result = yield from pf.run_commands_chain_async(preflight_chain, block=block, state_json_dir=state_json_dir)
    return result


def _add_copy_dcos_install(chain, local_install_path='/genconf/serve'):
    dcos_install_script = 'dcos_install.sh'
    local_install_path = os.path.join(local_install_path, dcos_install_script)
    remote_install_path = os.path.join(REMOTE_TEMP_DIR, dcos_install_script)
    chain.add_copy(local_install_path, remote_install_path, comment='COPYING dcos_install.sh TO TARGETS')


def _add_copy_packages(chain, local_pkg_base_path='/genconf/serve'):
    if not os.path.isfile(CLUSTER_PACKAGES_FILE):
        err_msg = '{} not found'.format(CLUSTER_PACKAGES_FILE)
        log.error(err_msg)
        raise ExecuteException(err_msg)

    cluster_packages = pkgpanda.load_json(CLUSTER_PACKAGES_FILE)
    for package, params in cluster_packages.items():
        destination_package_dir = os.path.join(REMOTE_TEMP_DIR, 'packages', package)
        local_pkg_path = os.path.join(local_pkg_base_path, params['filename'])

        chain.add_execute(['mkdir', '-p', destination_package_dir], comment='CREATING PKG DIR')
        chain.add_copy(local_pkg_path, destination_package_dir,
                       comment='COPYING PACKAGES TO TARGETS {}'.format(local_pkg_path))


def _add_copy_bootstap(chain, local_bs_path):
    remote_bs_path = REMOTE_TEMP_DIR + '/bootstrap'
    chain.add_execute(['mkdir', '-p', remote_bs_path], comment='CREATE DIR {}'.format(remote_bs_path))
    chain.add_copy(local_bs_path, remote_bs_path,
                   comment='COPYING BOOTSTRAP TO TARGETS (large file, can take up to 5min to transfer...)')


def _get_bootstrap_tarball(tarball_base_dir='/genconf/serve/bootstrap'):
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


@asyncio.coroutine
def install_dcos(config, block=False, state_json_dir=None, **kwargs):
    role = kwargs.get('role')
    roles = {
        'master': {
            'tags': {'role': 'master'},
            'hosts': config['master_list'],
            'chain_name': 'deploy_master',
            'script_parameter': 'master',
            'comment': 'INSTALLING DCOS ON MASTERS'
        },
        'agent': {
            'tags': {'role': 'agent'},
            'hosts': config['agent_list'],
            'chain_name': 'deploy_agent',
            'script_parameter': 'slave',
            'comment': 'INSTALLING DCOS ON AGENTS'
        }
    }
    assert role in roles, 'Role must be: {}'.format(roles.keys())
    default = roles.get(role)

    bootstrap_tarball = _get_bootstrap_tarball()
    log.debug('Start deploying {}'.format(role))
    log.debug("Local bootstrap found: %s", bootstrap_tarball)

    targets = []
    for host in default['hosts']:
        s = Server(host)
        s.add_tag(default['tags'])
        targets += [s]

    runner = get_async_runner(config, targets, **kwargs)
    chain = ssh.utils.CommandChain(default['chain_name'])

    add_pre_action(chain, runner.ssh_user)
    _add_copy_dcos_install(chain)
    _add_copy_packages(chain)
    _add_copy_bootstap(chain, bootstrap_tarball)

    chain.add_execute(['sudo', 'bash', '{}/dcos_install.sh'.format(REMOTE_TEMP_DIR), default['script_parameter']],
                      comment=default['comment'])
    add_post_action(chain)
    result = yield from runner.run_commands_chain_async(chain, block=block, state_json_dir=state_json_dir)
    return result


@asyncio.coroutine
def run_postflight(config, dcos_diag=None, block=False, state_json_dir=None, **kwargs):
    targets = []
    for host in config['master_list']:
        s = Server(host)
        s.add_tag({'role': 'master'})
        targets += [s]

    for host in config['agent_list']:
        s = Server(host)
        s.add_tag({'role': 'agent'})
        targets += [s]

    pf = get_async_runner(config, targets, **kwargs)
    postflight_chain = ssh.utils.CommandChain('postflight')
    add_pre_action(postflight_chain, pf.ssh_user)

    if dcos_diag is None:
        dcos_diag = '/opt/mesosphere/bin/dcos-diagnostics.py'

    postflight_chain.add_execute([dcos_diag], comment='Executing local post-flight check for DCOS servces...')
    add_post_action(postflight_chain)

    result = yield from pf.run_commands_chain_async(postflight_chain, block=block, state_json_dir=state_json_dir)
    return result


@asyncio.coroutine
def uninstall_dcos(config, block=False, state_json_dir=None, **kwargs):
    all_targets = config['master_list'] + config['agent_list']

    # clean the file to all targets
    runner = get_async_runner(config, all_targets, **kwargs)
    uninstall_chain = ssh.utils.CommandChain('uninstall')

    uninstall_chain.add_execute(['sudo', '-i', '/opt/mesosphere/bin/pkgpanda', 'uninstall', '&&', 'sudo', 'rm', '-rf',
                                 '/opt/mesosphere/'], comment='Uninstalling DCOS')
    result = yield from runner.run_commands_chain_async(uninstall_chain, block=block, state_json_dir=state_json_dir)
    return result
