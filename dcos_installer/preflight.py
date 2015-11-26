from ssh.remote_cmd import RemoteCmd
from dcos_installer.log import DCOSLog

log = DCOSLog(__name__).log


def check(options, config):
    """
    SSH via SubProcess Calls...
    """
    # Get a remote cmd object and set it up to execute the preflight script for masters
    preflight = RemoteCmd()
    preflight.ssh_user = config['ssh_user'] 
    preflight.ssh_key_path = config['ssh_key_path']
    preflight.inventory = config['master_list']
    preflight.log_directory = options.log_directory
    preflight.command = 'sudo bash /home/{}/install_dcos.sh --preflight-only'.format(config['ssh_user'])
    # Validate our inputs for the object are ok
    errors = preflight.validate()

    # If we got errors, show them; if not, execute preflight
    if len(errors) > 0:
        log.error("Could not execute preflight, errors encountered during validation.")
        for key, value in errors.items():
            log.error("%s: %s", key, value)
        return errors 
    else:
        preflight.execute()
        return False



