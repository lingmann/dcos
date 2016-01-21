import ssh.ssh_runner

REMOTE_TEMP_DIR = '/opt/dcos_install_tmp'
CLUSTER_PACKAGES_FILE = '/genconf/cluster_packages.json'


class ExecuteException(Exception): pass


def get_async_runner(config, hosts, **kwargs):
    process_timeout = config.get('process_timeout', 120)
    extra_ssh_options = config.get('extra_ssh_options', '')
    ssh_key_path = config.get('ssh_key_path', '/genconf/ssh_key')

    return ssh.ssh_runner.MultiRunner(hosts, ssh_user=config['ssh_user'], ssh_key_path=ssh_key_path,
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
