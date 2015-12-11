import os
import unittest
import unittest.mock

import deploy.deploy
import deploy.postflight
import deploy.preflight
import ssh.ssh_runner
from ssh.validate import ExecuteException, ValidationException


class TestDeploy(unittest.TestCase):
    def setUp(self):
        self.mocked_runner = unittest.mock.MagicMock()

    def tearDown(self):
        self.mocked_runner = None

    def test_handle_command_raise_execute_exception(self):
        self.mocked_runner.copy_cmd.return_value = [{'returncode': 1, 'stdout': 'stdout'}]
        with self.assertRaises(ExecuteException):
            deploy.deploy.copy_dcos_install(self.mocked_runner)

    def test_copy_dcos_install(self):
        deploy.deploy.copy_dcos_install(self.mocked_runner)
        self.mocked_runner.copy_cmd.assert_called_with('/genconf/serve/dcos_install.sh', '/tmp/')

    def test_copy_packages(self):
        deploy.deploy.copy_packages(self.mocked_runner)
        self.mocked_runner.copy_cmd.assert_called_with('/genconf/serve/packages/', '/tmp', recursive=True)

    def test_copy_bootstrap(self):
        deploy.deploy.copy_bootstrap(self.mocked_runner, '/genconf/serve/bootstrap')
        self.mocked_runner.execute_cmd.assert_called_with('mkdir -p /tmp/bootstrap/')
        self.mocked_runner.copy_cmd.assert_called_with('/genconf/serve/bootstrap', '/tmp/bootstrap/')

    @unittest.mock.patch('glob.glob')
    def test_get_bootstrap_tarball(self, mocked_glob):
        mocked_glob.return_value = ['pkg123']
        assert deploy.deploy.get_bootstrap_tarball() == 'pkg123'

    @unittest.mock.patch('ssh.ssh_runner.SSHRunner')
    def test_deploy_masters(self, mocked_ssh_runner):
        config = {
            'cluster_config': {
                'master_list': ['10.10.0.1']
            },
            'ssh_config': {
                'ssh_user': 'ubuntu',
                'ssh_key_path': '/home/ubuntu/.ssh/id_rsa',
                'log_directory': '/genconf/logs'
            }
        }
        deploy.deploy.deploy_masters(config)
        assert mocked_ssh_runner().ssh_user == 'ubuntu'
        assert mocked_ssh_runner().ssh_key_path == '/home/ubuntu/.ssh/id_rsa'
        assert mocked_ssh_runner().log_directory == '/genconf/logs'
        assert mocked_ssh_runner().targets == ['10.10.0.1']
        mocked_ssh_runner().execute_cmd.assert_called_with('sudo bash /tmp/dcos_install.sh master')

    @unittest.mock.patch('ssh.ssh_runner.SSHRunner')
    def test_deploy_agents(self, mocked_ssh_runner):
        config = {
            'cluster_config': {
                'master_list': ['10.10.0.1']
            },
            'ssh_config': {
                'ssh_user': 'ubuntu',
                'ssh_key_path': '/home/ubuntu/.ssh/id_rsa',
                'log_directory': '/genconf/logs',
                'target_hosts': ['10.10.0.2', '10.10.0.3']
            }
        }
        deploy.deploy.deploy_agents(config)
        assert mocked_ssh_runner().ssh_user == 'ubuntu'
        assert mocked_ssh_runner().ssh_key_path == '/home/ubuntu/.ssh/id_rsa'
        assert mocked_ssh_runner().log_directory == '/genconf/logs'
        assert '10.10.0.2' in mocked_ssh_runner().targets
        assert '10.10.0.3' in mocked_ssh_runner().targets
        mocked_ssh_runner().execute_cmd.assert_called_with('sudo bash /tmp/dcos_install.sh slave')

    @unittest.mock.patch('glob.glob')
    @unittest.mock.patch('ssh.ssh_runner.SSHRunner')
    def test_install_dcos(self, mocked_ssh_runner, mocked_glob):
        mocked_glob.return_value = ['pkg1']
        config = {
            'cluster_config': {
                'master_list': ['10.10.0.1']
            },
            'ssh_config': {
                'ssh_user': 'ubuntu',
                'ssh_key_path': '/home/ubuntu/.ssh/id_rsa',
                'log_directory': '/genconf/logs',
                'target_hosts': ['10.10.0.2', '10.10.0.3']
            }
        }
        deploy.deploy.install_dcos(config)

        assert mocked_ssh_runner().copy_cmd.call_count == 3
        mocked_ssh_runner().copy_cmd.assert_any_call('/genconf/serve/dcos_install.sh', '/tmp/')
        mocked_ssh_runner().copy_cmd.assert_any_call('/genconf/serve/packages/', '/tmp', recursive=True)
        mocked_ssh_runner().copy_cmd.assert_any_call('pkg1', '/tmp/bootstrap/')

        assert mocked_ssh_runner().execute_cmd.call_count == 3
        mocked_ssh_runner().execute_cmd.assert_any_call('mkdir -p /tmp/bootstrap/')
        mocked_ssh_runner().execute_cmd.assert_any_call('sudo bash /tmp/dcos_install.sh master')
        mocked_ssh_runner().execute_cmd.assert_any_call('sudo bash /tmp/dcos_install.sh slave')


class TestPreflight(unittest.TestCase):
    @unittest.mock.patch('ssh.ssh_runner.SSHRunner')
    def test_preflight_check(self, mocked_ssh_runner):
        config = {
            'cluster_config': {
                'master_list': ['10.10.0.1']
            },
            'ssh_config': {
                'ssh_user': 'ubuntu',
                'ssh_key_path': '/home/ubuntu/.ssh/id_rsa',
                'log_directory': '/genconf/logs',
                'target_hosts': ['10.10.0.2', '10.10.0.3']
            }
        }
        deploy.preflight.preflight_check(config, preflight_script_path='/somewhere/preflight.sh')
        mocked_ssh_runner().copy_cmd.assert_called_with('/somewhere/preflight.sh', '/tmp/')
        mocked_ssh_runner().execute_cmd.assert_called_with('sudo bash /tmp/preflight.sh')


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


if __name__ == '__main__':
    unittest.main()
