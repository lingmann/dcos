import paramiko
import multiprocessing as mp
from multiprocessing import Process
#from dcos_installer.ssh.execute import DCOSRemoteCmd
from ssh.execute import DCOSRemoteCmd
from dcos_installer.log import DCOSLog
log = DCOSLog(__name__).log



def check(options):
    """
    SSH via SubProcess Calls... 
    """
    # Set our SSH user, already validated.
    ssh_user = open(options.ssh_user_path, 'r').read().lstrip().rstrip()

    # Get a remote cmd object and set it up to execute the preflight script
    preflight = DCOSRemoteCmd()
    preflight.ssh_user = ssh_user 
    preflight.ssh_key_path = options.ssh_key_path
    preflight.inventory_path = options.hosts_yaml_path
    preflight.log_directory = options.log_directory
    preflight.command = 'sudo bash /home/{}/install_dcos.sh --preflight-only'.format(ssh_user)

    # Validate our inputs for the object are ok
    no_errors = preflight.validate()

    # If we got errors, show them; if not, execute preflight
    if not no_errors:
        log.error("Could not execute preflight, errors encountered during validation.", err)
        for key, value in no_errors.items():
            log.error("%s: %s", key, value)
        return no_errors 

    else:
        preflight.execute()
        return False 
