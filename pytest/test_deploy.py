import os
import unittest
import unittest.mock

import deploy.postflight
import ssh.ssh_runner
from ssh.validate import ExecuteException, ValidationException


class TestPostflight(unittest.TestCase):
    @unittest.mock.patch('subprocess.check_call')
    def test_run_integration_test(self, mocked_check_call):
        masters = '10.10.10.1,10.10.10.2'
        slaves = '10.10.10.3'
        dns_search = 'true'
        dcos_dns_address = 'http://10.10.10.1'
        registry_host = '10.10.10.1'
        env = os.environ.copy()
        env['MASTER_HOSTS'] = masters
        env['SLAVE_HOSTS'] = slaves
        env['REGISTRY_HOST'] = registry_host
        env['DNS_SEARCH'] = dns_search
        env['DCOS_DNS_ADDRESS'] = dcos_dns_address
        deploy.postflight.run_integration_test(masters, slaves, dns_search, dcos_dns_address, registry_host,
                                               test_path='/genconf')
        mocked_check_call.assert_called_with(['py.test', '-vv', '/genconf/integration_test.py'], env=env)

    @unittest.mock.patch('ssh.ssh_runner.SSHRunner.execute_cmd')
    @unittest.mock.patch('ssh.ssh_runner.SSHRunner.validate')
    def test_execute_local_service_check(self, mocked_validate, mocked_execute_cmd):
        executor = ssh.ssh_runner.SSHRunner()
        mocked_validate.return_value = []
        mocked_execute_cmd.return_value = [{'returncode': 0}]
        deploy.postflight.execute_local_service_check(executor)

    @unittest.mock.patch('ssh.ssh_runner.SSHRunner.validate')
    def test_execute_local_service_check_throw_validation_exception(self, mocked_validate):
        executor = ssh.ssh_runner.SSHRunner()
        mocked_validate.side_effect = ValidationException()
        with self.assertRaises(ValidationException):
            deploy.postflight.execute_local_service_check(executor)

    @unittest.mock.patch('ssh.ssh_runner.SSHRunner.execute_cmd')
    @unittest.mock.patch('ssh.ssh_runner.SSHRunner.validate')
    def test_execute_local_service_check_throw_execute_exception(self, mocked_validate, mocked_execute_cmd):
        executor = ssh.ssh_runner.SSHRunner()
        mocked_validate.return_value = []
        mocked_execute_cmd.return_value = [{'returncode': 1, 'stderr': 'stderr'}]
        with self.assertRaises(ExecuteException):
            deploy.postflight.execute_local_service_check(executor)
