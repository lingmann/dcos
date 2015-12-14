import logging
import os

import pkg_resources

from deploy.deploy import REMOTE_TEMP_DIR, cleanup_tmp_dir, init_tmp_dir
from deploy.util import create_full_inventory, get_runner
from ssh.utils import handle_command

log = logging.getLogger(__name__)


def preflight_check(preflight_runner, preflight_script_path):
    '''
    Copies preflight.sh to target hosts and executes the script. Gathers
    stdout, sterr and return codes and logs them to disk via SSH library.
    :param preflight_runner: ssh.ssh_runner.SSHRunner instance
    '''
    log.info("Executing Preflight")
    preflight_script_name = 'preflight.sh'
    if preflight_script_path is None:
        preflight_script_path = pkg_resources.resource_filename(__name__, preflight_script_name)

    handle_command(lambda: preflight_runner.copy_cmd(preflight_script_path, REMOTE_TEMP_DIR))
    handle_command(lambda: preflight_runner.execute_cmd('sudo bash {}'.format(os.path.join(REMOTE_TEMP_DIR,
                                                                              preflight_script_name))))


def run_preflight(config, preflight_script_path=None):
    '''
    Entry point function for preflight tests
    :param config: Dict, loaded config file from /genconf/config.yaml
    '''
    targets = create_full_inventory(config['cluster_config']['master_list'], config['ssh_config']['target_hosts'])
    preflight_runner = get_runner(config, targets)
    try:
        init_tmp_dir(preflight_runner)
        preflight_check(preflight_runner, preflight_script_path)
    finally:
        cleanup_tmp_dir(preflight_runner)
