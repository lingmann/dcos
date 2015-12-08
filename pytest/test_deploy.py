import os
import unittest
import unittest.mock

import deploy.postflight


class TestPostflight(unittest.TestCase):
    @unittest.mock.patch('subprocess.check_call')
    def test_run_integration_test(self, mocked_check_call):
        masters = '10.10.10.1,10.10.10.2'
        slaves = '10.10.10.3'
        dns_search = 'true'
        dcos_dns_address = 'http://10.10.10.1'
        registry_host = '10.10.10.1'
        deploy.postflight.run_integration_test(masters, slaves, dns_search, dcos_dns_address, registry_host,
                                               test_path='/genconf')
        mocked_check_call.assert_called_with('py.test -vv /genconf/integration_test.py', shell=True)
        assert os.environ['MASTER_HOSTS'] == masters
        assert os.environ['SLAVE_HOSTS'] == slaves
        assert os.environ['REGISTRY_HOST'] == registry_host
        assert os.environ['DNS_SEARCH'] == dns_search
        assert os.environ['DCOS_DNS_ADDRESS'] == dcos_dns_address

    @unittest.mock.patch('ssh.ssh_runner.SSHRunner.execute_cmd')
    @unittest.mock.patch('ssh.ssh_runner.SSHRunner.validate')
    def test_execute_local_service_check(self, mocked_validate, mocked_execute_cmd):
        ssh_user = 'ubuntu'
        ssh_key_path = '/home/ubuntu/.ssh/id_rsa'
        log_directory = '/genconf/logs'
        inventory = ['127.0.0.1']

        mocked_validate.return_value = []
        deploy.postflight.execute_local_service_check(ssh_user, ssh_key_path, log_directory, inventory)
        mocked_execute_cmd.assert_called_with('/opt/mesosphere/bin/dcos-diagnostics.py')

    @unittest.mock.patch('ssh.ssh_runner.SSHRunner.execute_cmd')
    @unittest.mock.patch('ssh.ssh_runner.SSHRunner.validate')
    def test_execute_local_service_check_with_errors(self, mocked_validate, mocked_execute_cmd):
        ssh_user = 'ubuntu'
        ssh_key_path = '/home/ubuntu/.ssh/id_rsa'
        log_directory = '/genconf/logs'
        inventory = ['127.0.0.1']

        mocked_validate.return_value = ['error1', 'error2']
        deploy.postflight.execute_local_service_check(ssh_user, ssh_key_path, log_directory, inventory)
        mocked_execute_cmd.assert_assert_not_called()
