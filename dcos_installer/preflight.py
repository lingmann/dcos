from ssh.remote_cmd import RemoteCmd
from dcos_installer.log import DCOSLog

log = DCOSLog(__name__).log


def check(options, config):
    """
    SSH via SubProcess Calls...
    """
    # Get a remote cmd object and set it up to execute the preflight script for masters
    log.info("Executing Preflight on Masters...")
    preflight_masters = RemoteCmd()
    preflight_masters.ssh_user = config['ssh_user'] 
    preflight_masters.ssh_key_path = config['ssh_key_path']
    preflight_masters.inventory = config['master_list']
    preflight_masters.log_directory = options.log_directory
    preflight_masters.command = 'sudo bash /home/{}/install_dcos.sh --preflight-only'.format(config['ssh_user'])
    # Validate our inputs for the object are ok
    errors_masters = preflight_masters.validate()

    # Run it again on slaves...
    log.info("Executing Preflight on Slaves...")
    preflight_agents = RemoteCmd()
    preflight_agents.ssh_user = config['ssh_user'] 
    preflight_agents.ssh_key_path = config['ssh_key_path']
    preflight_agents.inventory = config['agent_list']
    preflight_agents.log_directory = options.log_directory
    preflight_agents.command = 'sudo bash /home/{}/install_dcos.sh --preflight-only'.format(config['ssh_user'])
    # Validate our inputs for the object are ok
    errors_agents = preflight_agents.validate()

    # If we got errors, show them; if not, execute preflight
    if len(errors_masters) > 0 or len(errors_agents) > 0:
        log.error("Could not execute preflight, errors encountered during validation.")
        return_errors = {}
        if errors_masters:
            for key, value in errors_masters.items():
                log.error("%s: %s", key, value)
                return_errors[key] = value

        if errors_agents:
            for key, value in errors_agents.items():
                log.error("%s: %s", key, value)
                return_errors[key] = value

        return return_errors

    else:
        preflight_masters.execute()
        preflight_agents.execute()
        return False


