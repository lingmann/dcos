import ssh.ssh_runner


def create_full_inventory(master_list, targets):
    """
    Merge master and target lists together, ensure no duplicates
    """
    return list(set(master_list) | set(targets))


def create_agent_list(master_list, targets):
    """
    Return an array of targets excluding the masters.
    """
    return list(set(targets) - set(master_list))


def get_runner(config, hosts):
    """
    Retrun the with pre-set parameters.
    """
    default_runner = ssh.ssh_runner.SSHRunner()
    default_runner.ssh_user = config['ssh_config']['ssh_user']
    default_runner.ssh_key_path = config['ssh_config']['ssh_key_path']
    default_runner.log_directory = config['ssh_config']['log_directory']
    default_runner.targets = hosts
    default_runner.validate()
    return default_runner
