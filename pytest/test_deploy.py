import os
import unittest
import unittest.mock

import pkg_resources

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
        self.mocked_runner.copy_cmd.assert_called_with('/genconf/serve/dcos_install.sh',
                                                       '/opt/dcos_install_tmp/dcos_install.sh')

    @unittest.mock.patch('pkgpanda.load_json')
    @unittest.mock.patch('os.path.isfile')
    def test_copy_packages(self, mocked_isfile, mocked_load_json):
        mocked_isfile.return_value = True
        mocked_load_json.return_value = {
            "dcos-config": {
                "filename": "packages/dcos-config/dcos-config--setup_a1ddad12152a8b07982a910674cfcf320f9505b9.tar.xz",
                "id": "dcos-config--setup_a1ddad12152a8b07982a910674cfcf320f9505b9"
            }
        }
        deploy.deploy.copy_packages(self.mocked_runner)
        self.mocked_runner.copy_cmd.assert_called_with(
            '/genconf/serve/packages/dcos-config/dcos-config--setup_a1ddad12152a8b07982a910674cfcf320f9505b9.tar.xz',
            '/opt/dcos_install_tmp/packages/dcos-config')

    def test_copy_bootstrap(self):
        deploy.deploy.copy_bootstrap(self.mocked_runner, '/genconf/serve/bootstrap')
        self.mocked_runner.execute_cmd.assert_called_with('mkdir -p /opt/dcos_install_tmp/bootstrap')
        self.mocked_runner.copy_cmd.assert_called_with('/genconf/serve/bootstrap', '/opt/dcos_install_tmp/bootstrap')

    @unittest.mock.patch.dict(os.environ, {'BOOTSTRAP_ID': 'xyz'})
    @unittest.mock.patch('os.path.isfile')
    def test_get_bootstrap_tarball(self, mocked_isfile):
        mocked_isfile.return_value = True
        assert deploy.deploy.get_bootstrap_tarball(tarball_base_dir='/genconf/') == '/genconf/xyz.bootstrap.tar.xz'
        assert deploy.deploy.get_bootstrap_tarball() == '/genconf/serve/bootstrap/xyz.bootstrap.tar.xz'

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
        mocked_ssh_runner().execute_cmd.assert_called_with('sudo bash /opt/dcos_install_tmp/dcos_install.sh master')

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
        mocked_ssh_runner().execute_cmd.assert_called_with('sudo bash /opt/dcos_install_tmp/dcos_install.sh slave')

    @unittest.mock.patch.dict(os.environ, {'BOOTSTRAP_ID': 'xyz'})
    @unittest.mock.patch('pkgpanda.load_json')
    @unittest.mock.patch('os.path.isfile')
    @unittest.mock.patch('ssh.ssh_runner.SSHRunner')
    def test_install_dcos(self, mocked_ssh_runner, mocked_isfile, mocked_load_json):
        mocked_isfile.return_value = True
        mocked_load_json.return_value = {
            "dcos-config": {
                "filename": "packages/dcos-config/dcos-config--setup_a1ddad12152a8b07982a910674cfcf320f9505b9.tar.xz",
                "id": "dcos-config--setup_a1ddad12152a8b07982a910674cfcf320f9505b9"
            }
        }
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
        mocked_ssh_runner().copy_cmd.assert_any_call('/genconf/serve/dcos_install.sh',
                                                     '/opt/dcos_install_tmp/dcos_install.sh')
        mocked_ssh_runner().copy_cmd.assert_any_call(
            '/genconf/serve/packages/dcos-config/dcos-config--setup_a1ddad12152a8b07982a910674cfcf320f9505b9.tar.xz',
            '/opt/dcos_install_tmp/packages/dcos-config')
        mocked_ssh_runner().copy_cmd.assert_any_call('/genconf/serve/bootstrap/xyz.bootstrap.tar.xz',
                                                     '/opt/dcos_install_tmp/bootstrap')

        assert mocked_ssh_runner().execute_cmd.call_count == 7
        mocked_ssh_runner().execute_cmd.assert_any_call('mkdir -p /opt/dcos_install_tmp/bootstrap')
        mocked_ssh_runner().execute_cmd.assert_any_call('mkdir -p /opt/dcos_install_tmp/packages/dcos-config')
        mocked_ssh_runner().execute_cmd.assert_any_call('sudo bash /opt/dcos_install_tmp/dcos_install.sh master')
        mocked_ssh_runner().execute_cmd.assert_any_call('sudo bash /opt/dcos_install_tmp/dcos_install.sh slave')
        mocked_ssh_runner().execute_cmd.assert_any_call('sudo mkdir -p /opt/dcos_install_tmp')
        mocked_ssh_runner().execute_cmd.assert_any_call('sudo chown ubuntu /opt/dcos_install_tmp')
        mocked_ssh_runner().execute_cmd.assert_any_call('sudo rm -rf /opt/dcos_install_tmp')


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
        deploy.preflight.run_preflight(config, preflight_script_path='/somewhere/preflight.sh')
        assert mocked_ssh_runner().copy_cmd.call_count == 1
        mocked_ssh_runner().copy_cmd.assert_called_with('/somewhere/preflight.sh', '/opt/dcos_install_tmp')

        assert mocked_ssh_runner().execute_cmd.call_count == 4
        mocked_ssh_runner().execute_cmd.assert_any_call('sudo mkdir -p /opt/dcos_install_tmp')
        mocked_ssh_runner().execute_cmd.assert_any_call('sudo chown ubuntu /opt/dcos_install_tmp')
        mocked_ssh_runner().execute_cmd.assert_any_call('sudo bash /opt/dcos_install_tmp/preflight.sh')
        mocked_ssh_runner().execute_cmd.assert_any_call('sudo rm -rf /opt/dcos_install_tmp')

        deploy.preflight.run_preflight(config)
        prefligh_path = pkg_resources.resource_filename('deploy', 'preflight.sh')
        mocked_ssh_runner().copy_cmd.assert_called_with(prefligh_path, '/opt/dcos_install_tmp')


class TestPostflight(unittest.TestCase):
    @unittest.mock.patch('ssh.ssh_runner.SSHRunner.execute_cmd')
    @unittest.mock.patch('ssh.ssh_runner.SSHRunner.validate')
    def test_execute_local_service_check(self, mocked_validate, mocked_execute_cmd):
        executor = ssh.ssh_runner.SSHRunner()
        mocked_validate.return_value = []
        mocked_execute_cmd.return_value = [{'returncode': 0, 'stdout': 'stdout'}]
        deploy.postflight.execute_local_service_check(executor, None)

    @unittest.mock.patch('ssh.ssh_runner.SSHRunner.validate')
    def test_execute_local_service_check_throw_validation_exception(self, mocked_validate):
        executor = ssh.ssh_runner.SSHRunner()
        mocked_validate.side_effect = ValidationException()
        with self.assertRaises(ValidationException):
            deploy.postflight.execute_local_service_check(executor, None)

    @unittest.mock.patch('ssh.ssh_runner.SSHRunner.execute_cmd')
    @unittest.mock.patch('ssh.ssh_runner.SSHRunner.validate')
    def test_execute_local_service_check_throw_execute_exception(self, mocked_validate, mocked_execute_cmd):
        executor = ssh.ssh_runner.SSHRunner()
        mocked_validate.return_value = []
        mocked_execute_cmd.return_value = [{'returncode': 1, 'stderr': 'stderr', 'stdout': 'stdout'}]
        with self.assertRaises(ExecuteException):
            deploy.postflight.execute_local_service_check(executor, None)

    @unittest.mock.patch('subprocess.Popen')
    @unittest.mock.patch('ssh.ssh_runner.SSHRunner')
    def test_run_postflight(self, mocked_ssh_runner, mocked_popen):
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
        mocked_popen().pid = 123
        mocked_popen().returncode = 0
        mocked_popen().communicate.return_value = (bytes('stdout', encoding='utf-8'),
                                                   bytes('stderr', encoding='utf-8'))
        deploy.postflight.run_postflight(config)
        assert mocked_popen.call_count == 3
        assert mocked_ssh_runner().execute_cmd.call_count == 1
        mocked_ssh_runner().execute_cmd.assert_any_call('/opt/mesosphere/bin/dcos-diagnostics.py')


if __name__ == '__main__':
    unittest.main()
