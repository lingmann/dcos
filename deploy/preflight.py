import logging
import os

from deploy.util import create_full_inventory, get_runner
from ssh.utils import handle_command

log = logging.getLogger(__name__)


def preflight_check(config, preflight_script_path=None):
    """
    Copies preflight.sh to target hosts and executes the script. Gathers
    stdout, sterr and return codes and logs them to disk via SSH library.
    """
    # Implement copy...

    # Get a remote cmd object and set it up to execute the preflight script for masters
    log.info("Executing Preflight")
    if preflight_script_path is None:
        preflight_script_path = os.path.dirname(os.path.realpath(__file__)) + '/preflight.sh'
    preflight_remote_path = '/tmp/'

    targets = create_full_inventory(config['cluster_config']['master_list'], config['ssh_config']['target_hosts'])
    pf = get_runner(config, targets)

    handle_command(lambda: pf.copy_cmd(preflight_script_path, preflight_remote_path))
    handle_command(lambda: pf.execute_cmd('sudo bash /tmp/preflight.sh'))
