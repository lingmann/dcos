import logging as log
import os
import subprocess

from ssh.validate import ExecuteException, ValidationException


def run_integration_test(masters, slaves, dns_search, dcos_dns_address, registry_host, test_path=None,
                         pytest_path=None):
    '''
    Runs integration test against fully setup DCOS cluster
    python modules required to run integration test: pytest requests beautifulsoup4 kazoo retrying dnspython3
                                                     teamcity-messages
    :param masters: String: comma separated list of masters, for example: '127.0.0.1,127.0.0.2'
    :param slaves: String: comma separated list of slaves, for example: '127.0.0.1,127.0.0.2'
    :param dns_search: String: should be 'true' if /genconf/config.yaml ['cluster_config']['dns_search'] == 'mesos'
                               elese 'false'
    :param dcos_dns_address: String: any master with http prefix, for example: 'http://127.0.0.1'
    :param registry_host: String: any master host, for example '127.0.0.1'
    :param test_path: String: a path to dcos-image where integration-test.py lives
    :param pytest_path: String: a path to py.test
    :raises: ExecuteException if integration test fails
    '''
    env = os.environ.copy()
    env['MASTER_HOSTS'] = masters
    env['SLAVE_HOSTS'] = slaves
    env['REGISTRY_HOST'] = registry_host
    env['DNS_SEARCH'] = dns_search
    env['DCOS_DNS_ADDRESS'] = dcos_dns_address

    log.info('Running integration test')
    if test_path is None:
        test_path = os.getcwd()

    if pytest_path is None:
        pytest_path = 'py.test'

    command = [pytest_path, '-vv', '{}/integration_test.py'.format(test_path)]
    log.info(' '.join(command))
    try:
        subprocess.check_call(command, env=env)
    except subprocess.CalledProcessError:
        raise ExecuteException()


def execute_local_service_check(executor, dcos_diag=None):
    '''
    Execute post-flight check on local machine to ensure DCOS processes
    are in fact running.
    :param executor: configured instance of ssh.ssh_runner.SSHRunner
    :param dcos_diag: location of dcos-diagnostics.py
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

    for output in executor.execute_cmd(dcos_diag):
        if output['returncode'] != 0:
            log.error(output['stderr'])
            raise ExecuteException(output)
