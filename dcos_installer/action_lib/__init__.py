import asyncio
import json
import logging
import os

import pkgpanda
from ssh.ssh_runner import Node
from ssh.exceptions import ExecuteException
import ssh.utils

from .utils import REMOTE_TEMP_DIR, CLUSTER_PACKAGES_FILE, get_async_runner, add_post_action, add_pre_action
from .prettyprint import PrettyPrint

log = logging.getLogger(__name__)


@asyncio.coroutine
def run_preflight(config, pf_script_path='/genconf/serve/dcos_install.sh', block=False, state_json_dir=None,
                  async_delegate=None, retry=False, options=None):
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
        s = Node(host)
        s.add_tag({'role': 'master'})
        targets += [s]

    for host in config['agent_list']:
        s = Node(host)
        s.add_tag({'role': 'agent'})
        targets += [s]

    pf = get_async_runner(config, targets, async_delegate=async_delegate)
    chains = []

    preflight_chain = ssh.utils.CommandChain('preflight')
    # In web mode run if no --offline flag used.
    if options.web:
        if options.offline:
            log.debug('Offline mode used. Do not install prerequisites on CentOS7, RHEL7 in web mode')
        else:
            _add_prereqs_script(preflight_chain)

    add_pre_action(preflight_chain, pf.ssh_user)
    preflight_chain.add_copy(pf_script_path, REMOTE_TEMP_DIR, comment='COPYING PREFLIGHT SCRIPT TO TARGETS')

    preflight_chain.add_execute(
        'sudo bash {} --preflight-only master'.format(
            os.path.join(REMOTE_TEMP_DIR, os.path.basename(pf_script_path))).split(),
        comment='EXECUTING PREFLIGHT CHECK ON TARGETS')
    chains.append(preflight_chain)

    # Setup the cleanup chain
    cleanup_chain = ssh.utils.CommandChain('preflight_cleanup')
    add_post_action(cleanup_chain)

    chains.append(cleanup_chain)
    master_agent_count = {
        'total_masters': len(config['master_list']),
        'total_agents': len(config['agent_list'])
    }

    result = yield from pf.run_commands_chain_async(chains, block=block, state_json_dir=state_json_dir,
                                                    delegate_extra_params=master_agent_count)
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


def _remove_host(state_file, host):
    if not os.path.isfile(state_file):
        return False

    with open(state_file) as fh:
        json_state = json.load(fh)

    if 'hosts' not in json_state or host not in json_state['hosts']:
        return False

    log.debug('removing host {} from {}'.format(host, state_file))
    try:
        del json_state['hosts'][host]
    except KeyError:
        return False

    with open(state_file, 'w') as fh:
        json.dump(json_state, fh)

    return True


def _null_failed_counters(state_file):
    if not os.path.isfile(state_file):
        return False

    with open(state_file) as fh:
        json_state = json.load(fh)

    for failed_field in ['hosts_terminated', 'hosts_failed']:
        if failed_field not in json_state:
            continue
        log.debug('set {} to null'.format(failed_field))
        json_state[failed_field] = 0

    with open(state_file, 'w') as fh:
        json.dump(json_state, fh)


@asyncio.coroutine
def install_dcos(config, block=False, state_json_dir=None, hosts=[], async_delegate=None, try_remove_stale_dcos=False,
                 **kwargs):
    role = kwargs.get('role')
    roles = {
        'master': {
            'tags': {'role': 'master'},
            'hosts': hosts if hosts else config['master_list'],
            'chain_name': 'deploy_master',
            'script_parameter': 'master',
            'comment': 'INSTALLING DCOS ON MASTERS'
        },
        'agent': {
            'tags': {'role': 'agent'},
            'hosts': hosts if hosts else config['agent_list'],
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
        s = Node(host)
        s.add_tag(default['tags'])
        targets += [s]

    runner = get_async_runner(config, targets, async_delegate=async_delegate)
    chains = []
    if try_remove_stale_dcos:
        pkgpanda_uninstall_chain = ssh.utils.CommandChain('remove_stale_dcos')
        pkgpanda_uninstall_chain.add_execute(['sudo', '-i', '/opt/mesosphere/bin/pkgpanda', 'uninstall'],
                                             comment='TRYING pkgpanda uninstall')
        chains.append(pkgpanda_uninstall_chain)

        remove_dcos_chain = ssh.utils.CommandChain('remove_stale_dcos')
        remove_dcos_chain.add_execute(['rm', '-rf', '/opt/mesosphere', '/etc/mesosphere'])
        chains.append(remove_dcos_chain)

    chain = ssh.utils.CommandChain(default['chain_name'])
    chains.append(chain)

    add_pre_action(chain, runner.ssh_user)
    _add_copy_dcos_install(chain)
    _add_copy_packages(chain)
    _add_copy_bootstap(chain, bootstrap_tarball)

    chain.add_execute(['sudo', 'bash', '{}/dcos_install.sh'.format(REMOTE_TEMP_DIR), default['script_parameter']],
                      comment=default['comment'])

    if kwargs.get('retry') and state_json_dir:
        state_file_path = os.path.join(state_json_dir, '{}.json'.format(default['chain_name']))
        log.debug('retry executed for a state file {}'.format(state_file_path))
        for _host in default['hosts']:
            _remove_host(state_file_path, _host)

    # Setup the cleanup chain
    cleanup_chain = ssh.utils.CommandChain('{}_cleanup'.format(default['chain_name']))
    add_post_action(cleanup_chain)
    chains.append(cleanup_chain)

    result = yield from runner.run_commands_chain_async(chains, block=block,
                                                        state_json_dir=state_json_dir)
    return result


@asyncio.coroutine
def run_postflight(config, dcos_diag=None, block=False, state_json_dir=None, async_delegate=None, retry=False,
                   options=None):
    targets = []
    for host in config['master_list']:
        s = Node(host)
        s.add_tag({'role': 'master'})
        targets += [s]

    for host in config['agent_list']:
        s = Node(host)
        s.add_tag({'role': 'agent'})
        targets += [s]

    pf = get_async_runner(config, targets, async_delegate=async_delegate)
    postflight_chain = ssh.utils.CommandChain('postflight')
    add_pre_action(postflight_chain, pf.ssh_user)

    if dcos_diag is None:
        dcos_diag = """
#!/usr/bin/env bash
# Run the DCOS diagnostic script for up to 15 minutes (900 seconds) to ensure
# we do not return ERROR on a cluster that hasn't fully achieved quorum.
T=900
until OUT=$(/opt/mesosphere/bin/dcos-diagnostics.py) || [[ T -eq 0 ]]; do
    sleep 1
    let T=T-1
done
RETCODE=$?
for value in $OUT; do
    echo $value
done
exit $RETCODE"""

    postflight_chain.add_execute([dcos_diag], comment='Executing local post-flight check for DCOS servces...')
    add_post_action(postflight_chain)

    # Setup the cleanup chain
    cleanup_chain = ssh.utils.CommandChain('postflight_cleanup')
    add_post_action(cleanup_chain)

    master_agent_count = {
        'total_masters': len(config['master_list']),
        'total_agents': len(config['agent_list'])
    }

    result = yield from pf.run_commands_chain_async([postflight_chain, cleanup_chain], block=block,
                                                    state_json_dir=state_json_dir,
                                                    delegate_extra_params=master_agent_count)
    return result


@asyncio.coroutine
def uninstall_dcos(config, block=False, state_json_dir=None, async_delegate=None, options=None):
    all_targets = config['master_list'] + config['agent_list']

    # clean the file to all targets
    runner = get_async_runner(config, all_targets, async_delegate=async_delegate)
    uninstall_chain = ssh.utils.CommandChain('uninstall')

    uninstall_chain.add_execute([
        'sudo',
        '-i',
        '/opt/mesosphere/bin/pkgpanda',
        'uninstall',
        '&&',
        'sudo',
        'rm',
        '-rf',
        '/opt/mesosphere/'], comment='Uninstalling DCOS')
    result = yield from runner.run_commands_chain_async([uninstall_chain], block=block, state_json_dir=state_json_dir)

    return result


def _add_prereqs_script(chain):
    inline_script = """
#/bin/sh

dist=$(cat /etc/*-release | sed -n 's@^ID="\(.*\)"$@\\1@p')

if ([ x$dist != 'xrhel' ] && [ x$dist != 'xcentos' ]); then
  echo "$dist is not supported. Only RHEL and CentOS are supported" >&2
  exit 0
fi

version=$(cat /etc/*-release | sed -n 's@^VERSION_ID="\(.*\)"$@\\1@p')
if [ $version -lt 7 ]; then
  echo "$version is not supported. Only >= 7 version is supported" >&2
  exit 0
fi

sudo tee /etc/yum.repos.d/docker.repo <<-'EOF'
[dockerrepo]
name=Docker Repository
baseurl=https://yum.dockerproject.org/repo/main/centos/$releasever/
enabled=1
gpgcheck=1
gpgkey=https://yum.dockerproject.org/gpg
EOF

sudo yum -y update

sudo yum install -y docker-engine
sudo echo "STORAGE_DRIVER=overlay" >> /etc/sysconfig/docker-storage-setup
sudo systemctl start docker
sudo systemctl enable docker

sudo yum install -y wget
sudo yum install -y git
sudo yum install -y unzip
sudo yum install -y curl
sudo yum install -y xz

sudo getent group nogroup || sudo groupadd nogroup
"""
    # Run a first command to get json file generated.
    chain.add_execute(['echo', 'INSTALL', 'PREREQUISITES'])
    chain.add_execute([inline_script], comment='INSTALLING PREFLIGHT PREREQUISITES')


@asyncio.coroutine
def install_prereqs(config, block=False, state_json_dir=None, async_delegate=None, options=None):
    all_targets = config['master_list'] + config['agent_list']
    runner = get_async_runner(config, all_targets, async_delegate=async_delegate)
    prereqs_chain = ssh.utils.CommandChain('install_prereqs')
    _add_prereqs_script(prereqs_chain)
    result = yield from runner.run_commands_chain_async([prereqs_chain], block=block, state_json_dir=state_json_dir)
    return result
