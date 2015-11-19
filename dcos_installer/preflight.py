import paramiko
import multiprocessing as mp
from multiprocessing import Process
from dcos_installer.ssh.execute import DCOSRemoteCmd
from dcos_installer.log import DCOSLog
log = DCOSLog(__name__).log



def check(options):
    """
    SSH via SubProcess Calls... 
    """
    ssh_user = open(options.ssh_user_path, 'r').read().lstrip().rstrip()

    preflight = DCOSRemoteCmd()
    preflight.ssh_user = ssh_user 
    preflight.ssh_key_path = options.ssh_key_path
    preflight.inventory_path = options.hosts_yaml_path
    preflight.log_directory = options.log_directory
    preflight.command = 'sudo bash /home/{}/install_dcos.sh --preflight-only'.format(ssh_user)
    err = preflight.validate()
    if err:
        log.error("Could not execute preflight, errors encountered during validation.")
        log.error(err)

    else:
        preflight.execute()
