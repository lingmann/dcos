import logging
import os

from deploy.console_printer import clean_logs, print_failures, print_header
from deploy.util import (REMOTE_TEMP_DIR, cleanup_tmp_dir,
                         create_full_inventory, deploy_handler, get_runner,
                         init_tmp_dir)

log = logging.getLogger(__name__)


def copy_preflight(pf, pf_script_path):
    print_header('COPYING PREFLIGHT SCRIPT TO TARGETS')
    deploy_handler(
        lambda: pf.copy_cmd(pf_script_path, REMOTE_TEMP_DIR))


def execute_preflight(pf):
    print_header('EXECUTING PREFLIGHT CHECK ON TARGETS')
    preflight_script_name = 'dcos_install.sh'
    deploy_handler(
        lambda: pf.execute_cmd(
            'sudo bash {} --preflight-only master'.format(os.path.join(REMOTE_TEMP_DIR, preflight_script_name))),
        'print_data_preflight')


def run_preflight(config, pf_script_path='/genconf/serve/dcos_install.sh'):
    '''
    Copies preflight.sh to target hosts and executes the script. Gathers
    stdout, sterr and return codes and logs them to disk via SSH library.
    :param config: Dict, loaded config file from /genconf/config.yaml
    :param pf_script_path: preflight.sh script location on a local host
    :param preflight_remote_path: destination location
    '''
    clean_logs('preflight', config['ssh_config']['log_directory'])
    if not os.path.isfile(pf_script_path):
        log.error("genconf/serve/dcos_install.sh does not exist. Please run --genconf before executing preflight.")
        raise FileNotFoundError('genconf/serve/dcos_install.sh does not exist')
    targets = create_full_inventory(config)
    pf = get_runner(config, targets, 'preflight')
    try:
        init_tmp_dir(pf)
        copy_preflight(pf, pf_script_path)
        execute_preflight(pf)
    finally:
        cleanup_tmp_dir(pf)
        print_failures('preflight', config['ssh_config']['log_directory'])
