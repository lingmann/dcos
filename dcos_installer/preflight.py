from ssh.remote_cmd import RemoteCmd
from dcos_installer.log import DCOSLog

log = DCOSLog(__name__).log


def check(options):
    """
    SSH via SubProcess Calls...
    """
    # Set our SSH user, already validated.
    ssh_user = open(options.ssh_user_path, 'r').read().lstrip().rstrip()

    # Get a remote cmd object and set it up to execute the preflight script
    preflight = RemoteCmd()
    preflight.ssh_user = ssh_user 
    preflight.ssh_key_path = options.ssh_key_path
    preflight.inventory_path = options.hosts_yaml_path
    preflight.log_directory = options.log_directory
    preflight.command = 'sudo bash /home/{}/install_dcos.sh --preflight-only'.format(ssh_user)

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
