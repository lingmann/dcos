import logging
import os

import pkg_resources

from deploy.deploy import REMOTE_TEMP_DIR
from deploy.util import create_full_inventory, get_runner
from ssh.utils import handle_command

log = logging.getLogger(__name__)


def preflight_check(config, preflight_script_path=None):
    '''
    Copies preflight.sh to target hosts and executes the script. Gathers
    stdout, sterr and return codes and logs them to disk via SSH library.
    :param config: Dict, loaded config file from /genconf/config.yaml
    :param preflight_script_path: preflight.sh script location on a local host
    :param preflight_remote_path: destination location
    '''
    log.info("Executing Preflight")
    preflight_script_name = 'preflight.sh'
    if preflight_script_path is None:
        preflight_script_path = pkg_resources.resource_filename(__name__, preflight_script_name)

    targets = create_full_inventory(config['cluster_config']['master_list'], config['ssh_config']['target_hosts'])
    pf = get_runner(config, targets)

    handle_command(lambda: pf.copy_cmd(preflight_script_path, REMOTE_TEMP_DIR))
    handle_command(lambda: pf.execute_cmd('sudo bash {}'.format(os.path.join(REMOTE_TEMP_DIR,
                                                                             preflight_script_name))))
