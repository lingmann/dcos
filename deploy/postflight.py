import ssh.ssh_runner
import logging as log
import subprocess
import os

from ssh.validate import ValidationException, ExecuteException


def run_integration_test(masters, slaves, dns_search, dcos_dns_address, registry_host, test_path=None,
                         pytest_path=None):
    """
    python modules required to run integration test: pytest requests beautifulsoup4 kazoo retrying dnspython3
                                                     teamcity-messages
    """
    os.environ['MASTER_HOSTS'] = masters
    os.environ['SLAVE_HOSTS'] = slaves
    os.environ['REGISTRY_HOST'] = registry_host
    os.environ['DNS_SEARCH'] = dns_search
    os.environ['DCOS_DNS_ADDRESS'] = dcos_dns_address
    log.debug(os.environ)
    log.info('Running integration test')
    if test_path is None:
        test_path = os.getcwd()

    if pytest_path is None:
        pytest_path = 'py.test'

    print(os.environ)
    command = '{} -vv {}/integration_test.py'.format(pytest_path, test_path)
    log.info('Run> {}'.format(command))
    try:
        subprocess.check_call(command, shell=True)
    except subprocess.SubprocessError as err:
        log.error(err)
        raise


def execute_local_service_check(ssh_user, ssh_key_path, log_directory, inventory):
    """
    Execute post-flight check on local machine to ensure DCOS processes
    are in fact running.
    """
    log.info("Executing local post-flight check for DCOS servces...")
    pf = ssh.ssh_runner.SSHRunner()
    pf.ssh_user = ssh_user
    pf.ssh_key_path = ssh_key_path
    pf.log_directory = log_directory
    pf.targets = inventory

    try:
        pf.validate()
    except ValidationException as err:
        log.error(err)
        raise

    for output in pf.execute_cmd('/opt/mesosphere/bin/dcos-diagnostics.py'):
        if output['returncode'] != 0:
            log.error(output['stderr'])
            raise ExecuteException(output)
