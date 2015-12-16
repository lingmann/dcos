import logging as log

from deploy.util import create_full_inventory, get_runner
from ssh.utils import handle_command
from ssh.validate import ValidationException


def execute_local_service_check(executor, dcos_diag):
    '''
    Execute post-flight check on local machine to ensure DCOS processes
    are in fact running.
    :param executor: configured instance of ssh.ssh_runner.SSHRunner
    :param dcos_diag: remote location of dcos-diagnostics.py
    :raises: ssh.validate.ValidationException if config validation fails
             ssh.validate.ExecuteException if command execution fails
    '''
    if dcos_diag is None:
        dcos_diag = '/opt/mesosphere/bin/dcos-diagnostics.py'

    log.info("Executing local post-flight check for DCOS servces...")
    try:
        executor.validate()
    except ValidationException as err:
        log.error(err)
        raise

    handle_command(lambda: executor.execute_cmd(dcos_diag))


def run_postflight(config, dcos_diag=None):
    '''
    Entry point for postflight tests
    :param config: Dict, loaded config file from /genconf/config.yaml
    :param test_path: String, a path to dcos-image where integration-test.py lives
    :param pytest_path: String: a path to py.test
    :param dcos_diag: remote location of dcos-diagnostics.py
    '''
    postflight_runner = get_runner(config, create_full_inventory(config))
    execute_local_service_check(postflight_runner, dcos_diag)
