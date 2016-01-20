import logging

import ssh.ssh_runner
from deploy.console_printer import print_header
from deploy.prettyprint import PrettyPrint

REMOTE_TEMP_DIR = '/opt/dcos_install_tmp'
CLUSTER_PACKAGES_FILE = '/genconf/cluster_packages.json'

log = logging.getLogger(__name__)


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


def get_runner(config, hosts, log_postfix):
    '''

    :param config: Dict, loaded config file from /genconf/config.yaml
    :param hosts: set hosts to run ssh commands on
    :return: instance of ssh.ssh_runner.SSHRunner with pre-set parameters.
    '''
    default_runner = ssh.ssh_runner.SSHRunner()
    # process timeout and ssh options are defualted in ssh lib, so override if they're set or
    # accept defaults
    if 'extra_ssh_options' in config['ssh_config']:
        default_runner.extra_ssh_options = config['ssh_config']['extra_ssh_options']
    if 'process_timeout' in config['ssh_config']:
        default_runner.process_timeout = config['ssh_config']['process_timeout']
    default_runner.log_postfix = log_postfix
    default_runner.ssh_user = config['ssh_config']['ssh_user']
    if 'ssh_key_path' in config['ssh_config']:
        default_runner.ssh_key_path = config['ssh_config']['ssh_key_path']
    else:
        default_runner.ssh_key_path = '/genconf/ssh_key'
    # Default the log directory so we don't need to set it in config, otherwise
    # override if it's present
    if 'log_directory' in config['ssh_config']:
        default_runner.log_directory = config['ssh_config']['log_directory']
    else:
        default_runner.log_directory = '/genconf/logs'
    default_runner.targets = hosts
    default_runner.validate()
    return default_runner


def init_tmp_dir(runner):
    print_header('CREATING TEMP DIRECTORY ON TARGETS')
    deploy_handler(lambda: runner.execute_cmd('sudo mkdir -p {}'.format(REMOTE_TEMP_DIR)))
    print_header('ENSURING {} OWNS TEMPORARY DIRECTORY'.format(runner.ssh_user))
    deploy_handler(
        lambda: runner.execute_cmd('sudo chown {} {}'.format(runner.ssh_user, REMOTE_TEMP_DIR)))


def cleanup_tmp_dir(runner):
    print_header('CLEANING UP TEMPORARY DIRECTORIES ON TARGETS')
    deploy_handler(lambda: runner.execute_cmd('sudo rm -rf {}'.format(REMOTE_TEMP_DIR)))


def deploy_handler(command, print_mode='print_data_basic'):
    failed = []
    success = []
    for output in command():
        pretty_out = PrettyPrint(output)
        f, s = pretty_out.beautify(print_mode)
        failed.append(f)
        success.append(s)

    return failed, success
