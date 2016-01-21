import ssh.ssh_runner

REMOTE_TEMP_DIR = '/opt/dcos_install_tmp'
CLUSTER_PACKAGES_FILE = '/genconf/cluster_packages.json'


class ExecuteException(Exception): pass


def create_full_inventory(config):
    '''
    Join 2 lists of masters and all hosts to make sure we are addressing all available hosts.
    :config Dict, /genconf/config.yaml object
    :return: joined unique list of masters and all targets
    '''
    return list(set(config['cluster_config']['master_list']) | set(config['ssh_config']['target_hosts']))


def create_agent_list(config):
    '''
    Agents are targets - masters
    :config Dict, /genconf/config.yaml object
    :return: List  of targets excluding the masters.
    '''
    return list(set(config['ssh_config']['target_hosts']) - set(config['cluster_config']['master_list']))


def get_async_runner(config, hosts, **kwargs):
    process_timeout = config['ssh_config'].get('process_timeout', 120)
    extra_ssh_options = config['ssh_config'].get('extra_ssh_options', '')
    ssh_key_path = config['ssh_config'].get('ssh_key_path', '/genconf/ssh_key')

    return ssh.ssh_runner.MultiRunner(hosts, ssh_user=config['ssh_config']['ssh_user'], ssh_key_path=ssh_key_path,
                                      process_timeout=process_timeout, extra_opts=extra_ssh_options, **kwargs)

def add_pre_action(chain, ssh_user):
    # Do setup steps for a chain
    chain.add_execute(['sudo', 'mkdir', '-p', REMOTE_TEMP_DIR], comment='CREATING TEMP DIRECTORY ON TARGETS')
    chain.add_execute(['sudo', 'chown', ssh_user, REMOTE_TEMP_DIR],
                      comment='ENSURING {} OWNS TEMPORARY DIRECTORY'.format(ssh_user))


def add_post_action(chain):
    # Do cleanup steps for a chain
    chain.add_execute(['sudo', 'rm', '-rf', REMOTE_TEMP_DIR],
                      comment='CLEANING UP TEMPORARY DIRECTORIES ON TARGETS')
