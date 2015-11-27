# Example usage from genconf.py:
# from . import deploy.copy
# copy.copy_to_targets(config, '/local/path', 'remote_path'

from ssh.log import SSHLog
from ssh.remote_copy import RemoteCopy
log = SSHLog(__name__).log

def copy_to_targets(config, log_directory, local_path, remote_path):
    log.info(config)
    copy_mstr = RemoteCopy()
    copy_mstr.ssh_user = config['ssh_user']
    copy_mstr.ssh_key_path = config['ssh_key_path']
    copy_mstr.inventory = config['master_list']
    copy_mstr.local_path = local_path
    copy_mstr.remote_path = remote_path
    copy_mstr.log_directory = log_directory

    copy_agent = RemoteCopy()
    copy_agent.ssh_user = config['ssh_user']
    copy_agent.ssh_key_path = config['ssh_key_path']
    copy_agent.inventory = config['agent_list']
    copy_agent.local_path = local_path
    copy_agent.remote_path = remote_path
    copy_agent.log_directory = log_directory

    log.info("Validating master copy object...")
    mstr_err = copy_mstr.validate()
    log.info("Validating agent copy object...")
    agent_err = copy_agent.validate()

    if mstr_err or agent_err:
        if mstr_err:
            log.error(mstr_err)
            return mstr_err

        elif agent_err:
            log.error(agent_err)
            return agent_err

    else:
        log.info("Executing remote copy to masters...")
        copy_mstr.transfer()
        log.info("Executing remote copy to agents...")
        copy_agent.transfer()
        return False
