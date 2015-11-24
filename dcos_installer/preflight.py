from ssh.remote_cmd import RemoteCmd
from dcos_installer.log import DCOSLog

log = DCOSLog(__name__).log


def check(ssh_options):
    """
    SSH via SubProcess Calls...
    """
    # Set our SSH user, already validated.
    ssh_user = open(options.ssh_user_path, 'r').read().lstrip().rstrip()

    # Get a remote cmd object and set it up to execute the preflight script for masters
    preflight = RemoteCmd()
    preflight.ssh_user = ssh_options['ssh_user'] 
    preflight.ssh_key_path = ssh_options['ssh_key_path']
    preflight.inventory = ssh_options['master_list']
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



