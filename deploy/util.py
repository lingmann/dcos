import ssh.ssh_runner


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


def get_runner(config, hosts):
    '''

    :param config: Dict, loaded config file from /genconf/config.yaml
    :param hosts: set hosts to run ssh commands on
    :return: instance of ssh.ssh_runner.SSHRunner with pre-set parameters.
    '''
    default_runner = ssh.ssh_runner.SSHRunner()
    default_runner.ssh_user = config['ssh_config']['ssh_user']
    default_runner.ssh_key_path = config['ssh_config']['ssh_key_path']
    default_runner.log_directory = config['ssh_config']['log_directory']
    default_runner.targets = hosts
    default_runner.validate()
    return default_runner
