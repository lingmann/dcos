import os
import tempfile
import unittest
import unittest.mock

import ssh.ssh_runner
import ssh.validate


class TestMultiRunner(unittest.TestCase):
    def setUp(self):
        self.multirunner = ssh.ssh_runner.MultiRunner(['127.0.0.1', '10.10.10.10:22022'], ssh_user='ubuntu',
                                                      ssh_key_path='/home/ubuntu/.ssh/id_rsa')

    def tearDown(self):
        pass

    def test_parse_ip(self):
        assert ssh.ssh_runner.parse_ip('127.0.0.1') == {'ip': '127.0.0.1', 'port': 22}
        assert ssh.ssh_runner.parse_ip('127.0.0.1:22022') == {'ip': '127.0.0.1', 'port': 22022}

    @unittest.mock.patch('subprocess.Popen')
    def test_run_cmd_return_tuple(self, mocked_popen):
        mocked_popen().communicate.return_value = ('stdout\nnewline'.encode(), 'stderr\nnewline'.encode())
        mocked_popen().pid = 1111
        mocked_popen().returncode = 0
        assert ssh.ssh_runner.run_cmd_return_tuple('127.0.0.1', ['uname', '-a']) == \
            {
                'cmd': ['uname', '-a'],
                'host': '127.0.0.1',
                'pid': 1111,
                'returncode': 0,
                'stderr': ['stderr', 'newline'],
                'stdout': ['stdout', 'newline']
            }

    @unittest.mock.patch('subprocess.Popen')
    def test_multirunner_run(self, mocked_popen):
        mocked_popen().communicate.return_value = ('stdout\nnewline'.encode(), 'stderr\nnewline'.encode())
        mocked_popen().pid = 1111
        mocked_popen().returncode = 0
        assert self.multirunner.run(['uname', '-a']) == [
            {
                "stdout": ["stdout", "newline"],
                "returncode": 0,
                "host": {"port": 22, "ip": "127.0.0.1"},
                "stderr": ["stderr", "newline"],
                "pid": 1111,
                "cmd": ["/usr/bin/ssh", "-oConnectTimeout=3", "-oStrictHostKeyChecking=no",
                        "-oUserKnownHostsFile=/dev/null", "-p22", "-i", "/home/ubuntu/.ssh/id_rsa", "ubuntu@127.0.0.1",
                        "uname", "-a"]
            },
            {
                "stdout": ["stdout", "newline"],
                "returncode": 0,
                "host": {"port": 22022, "ip": "10.10.10.10"},
                "stderr": ["stderr", "newline"],
                "pid": 1111,
                "cmd": ["/usr/bin/ssh", "-oConnectTimeout=3", "-oStrictHostKeyChecking=no",
                        "-oUserKnownHostsFile=/dev/null", "-p22022", "-i", "/home/ubuntu/.ssh/id_rsa",
                        "ubuntu@10.10.10.10", "uname", "-a"]
            }]

    @unittest.mock.patch('subprocess.Popen')
    def test_multirunner_copy(self, mocked_popen):
        mocked_popen().communicate.return_value = ('stdout\nnewline'.encode(), 'stderr\nnewline'.encode())
        mocked_popen().pid = 1111
        mocked_popen().returncode = 0
        assert self.multirunner.copy('/tmp/pilot.txt', '/usr') == [
            {
                "stdout": ["stdout", "newline"],
                "returncode": 0,
                "host": {"port": 22, "ip": "127.0.0.1"},
                "stderr": ["stderr", "newline"],
                "pid": 1111,
                "cmd": ["/usr/bin/scp", "-oConnectTimeout=3", "-oStrictHostKeyChecking=no",
                        "-oUserKnownHostsFile=/dev/null", "-P22", "-i", "/home/ubuntu/.ssh/id_rsa",
                        "/tmp/pilot.txt", "ubuntu@127.0.0.1:/usr"]
            },
            {
                "stdout": ["stdout", "newline"],
                "returncode": 0,
                "host": {"port": 22022, "ip": "10.10.10.10"},
                "stderr": ["stderr", "newline"],
                "pid": 1111,
                "cmd": ["/usr/bin/scp", "-oConnectTimeout=3", "-oStrictHostKeyChecking=no",
                        "-oUserKnownHostsFile=/dev/null", "-P22022", "-i", "/home/ubuntu/.ssh/id_rsa",
                        "/tmp/pilot.txt", "ubuntu@10.10.10.10:/usr"]
            }]

    @unittest.mock.patch('subprocess.Popen')
    def test_multirunner_copy_recursive(self, mocked_popen):
        mocked_popen().communicate.return_value = ('stdout\nnewline'.encode(), 'stderr\nnewline'.encode())
        mocked_popen().pid = 1111
        mocked_popen().returncode = 0
        assert self.multirunner.copy('/tmp/pilot.txt', '/usr', recursive=True) == [
            {
                "stdout": ["stdout", "newline"],
                "returncode": 0,
                "host": {"port": 22, "ip": "127.0.0.1"},
                "stderr": ["stderr", "newline"],
                "pid": 1111,
                "cmd": ["/usr/bin/scp", "-oConnectTimeout=3", "-oStrictHostKeyChecking=no",
                        "-oUserKnownHostsFile=/dev/null", "-P22", "-i", "/home/ubuntu/.ssh/id_rsa", "-r",
                        "/tmp/pilot.txt", "ubuntu@127.0.0.1:/usr"]
            },
            {
                "stdout": ["stdout", "newline"],
                "returncode": 0,
                "host": {"port": 22022, "ip": "10.10.10.10"},
                "stderr": ["stderr", "newline"],
                "pid": 1111,
                "cmd": ["/usr/bin/scp", "-oConnectTimeout=3", "-oStrictHostKeyChecking=no",
                        "-oUserKnownHostsFile=/dev/null", "-P22022", "-i", "/home/ubuntu/.ssh/id_rsa", "-r",
                        "/tmp/pilot.txt", "ubuntu@10.10.10.10:/usr"]
            }]


class TestSSHRunner(unittest.TestCase):
    def setUp(self):
        self.ssh_runner = ssh.ssh_runner.SSHRunner()
        self.ssh_runner.ssh_user = 'ubuntu'
        self.ssh_runner.log_directory = '/tmp'
        self.ssh_runner.ssh_key_path = '/home/ubuntu/.ssh/id_rsa'
        self.ssh_runner.targets = ['127.0.0.1', '10.10.10.10:22022']

    @unittest.mock.patch('ssh.ssh_runner.SSHRunner.validate')
    @unittest.mock.patch('ssh.ssh_runner.MultiRunner')
    def test_execute_cmd(self, mocked_multirunner, mocked_validate):
        mocked_validate.return_value = True
        mocked_multirunner().run.return_result = [
            {
                "stdout": ["stdout", "newline"],
                "returncode": 0,
                "host": {"port": 22, "ip": "127.0.0.1"},
                "stderr": ["stderr", "newline"],
                "pid": 1111,
                "cmd": ["/usr/bin/ssh", "-oConnectTimeout=3", "-oStrictHostKeyChecking=no",
                        "-oUserKnownHostsFile=/dev/null", "-p22", "-i", "/home/ubuntu/.ssh/id_rsa", "ubuntu@127.0.0.1",
                        "uname", "-a"]
            },
            {
                "stdout": ["stdout", "newline"],
                "returncode": 0,
                "host": {"port": 22022, "ip": "10.10.10.10"},
                "stderr": ["stderr", "newline"],
                "pid": 1111,
                "cmd": ["/usr/bin/ssh", "-oConnectTimeout=3", "-oStrictHostKeyChecking=no",
                        "-oUserKnownHostsFile=/dev/null", "-p22022", "-i", "/home/ubuntu/.ssh/id_rsa",
                        "ubuntu@10.10.10.10", "uname", "-a"]
            }]

        self.ssh_runner.execute_cmd('uname -a')
        mocked_multirunner.assert_called_with(['127.0.0.1', '10.10.10.10:22022'], ssh_user='ubuntu',
                                              ssh_key_path='/home/ubuntu/.ssh/id_rsa')
        mocked_multirunner().run.assert_called_with(['uname', '-a'])

    @unittest.mock.patch('time.strftime')
    @unittest.mock.patch('ssh.helpers.dump_host_results')
    def test_save_log(self, mocked_dump_host_results, mocked_time_strftime):
        mock_struct_data = [
            {
                'host': {
                    'ip': '127.0.0.1'
                }
            }
        ]
        mocked_time_strftime.return_value = '123'
        self.ssh_runner.save_logs(mock_struct_data)
        mocked_dump_host_results.assert_called_with('/tmp', '127.0.0.1',
                                                    {'127.0.0.1': {'123': {'host': {'ip': '127.0.0.1'}}}})

    @unittest.mock.patch('ssh.ssh_runner.SSHRunner.save_logs')
    def test_wrapped_run_no_cache(self, mocked_save_logs):
        func = lambda: [{'returncode': 0}]
        self.ssh_runner.use_cache = False
        self.ssh_runner.wrapped_run(func)
        mocked_save_logs.assert_called_with([{'returncode': 0}])

    @unittest.mock.patch('json.dump')
    @unittest.mock.patch('json.load')
    @unittest.mock.patch('builtins.open')
    @unittest.mock.patch('os.path.isfile')
    @unittest.mock.patch('ssh.ssh_runner.SSHRunner.save_logs')
    def test_wrapped_run_use_cache(self, mocked_save_logs, mocked_isfile, mocked_open, mocked_json_load,
                                   mocked_json_dump):
        func = lambda: [{'returncode': 0, 'host': {'ip': '127.0.0.1'}}]
        self.ssh_runner.use_cache = True
        mocked_isfile.return_value = True

        self.ssh_runner.wrapped_run(func)
        mocked_save_logs.assert_called_with([{'returncode': 0, 'host': {'ip': '127.0.0.1'}}])
        assert mocked_open.call_count == 2
        mocked_open.assert_any_call('./.cache.json')
        mocked_open.assert_called_with('./.cache.json', 'w')
        assert mocked_json_load.call_count == 1
        assert mocked_json_dump.call_count == 1

    @unittest.mock.patch('ssh.ssh_runner.SSHRunner.validate')
    @unittest.mock.patch('ssh.ssh_runner.MultiRunner.copy')
    def test_copy_cmd(self, mocked_copy, mocked_validate):
        mocked_validate.return_value = True
        self.ssh_runner.copy_cmd('/tmp/test.txt', '/tmp')
        mocked_copy.assert_called_with('/tmp/test.txt', '/tmp', remote_to_local=False, recursive=False)
        self.ssh_runner.copy_cmd('/tmp/test.txt', '/tmp', recursive=True)
        mocked_copy.assert_called_with('/tmp/test.txt', '/tmp', remote_to_local=False, recursive=True)
        self.ssh_runner.copy_cmd('/tmp/local.txt', '/tmp/remote.txt', remote_to_local=True)
        mocked_copy.assert_called_with('/tmp/local.txt', '/tmp/remote.txt', remote_to_local=True, recursive=False)

    def test_validate_dont_raise_exception(self):
        runner = ssh.ssh_runner.SSHRunner()
        runner.targets = ['127.0.0.1', '127.0.0.2:22022']
        validation_result = runner.validate(throw_if_errors=False)
        expected_errors = {
            'log_directory must not be None',
            'ssh_user must not be None',
            'ssh_key_path must not be None',
            'log_directory must be str',
            'ssh_user must be str',
            'ssh_key_path must be str',
            'ssh_key_path file None does not exist on filesystem',
            'log_directory directory None does not exist on filesystem',
            'Cannot specify None for path argument'
        }
        assert set(validation_result) - set(expected_errors) == set()

    def test_validate_raise_exception(self):
        runner = ssh.ssh_runner.SSHRunner()
        runner.ssh_key_path = '/no_file_exists'
        runner.log_directory = '/no_dir_exists'

        try:
            runner.validate()
        except ssh.validate.ValidationException as err:
            expected_errors = {
                'ssh_user must not be None',
                'ssh_user must be str',
                'ssh_key_path file /no_file_exists does not exist on filesystem',
                'log_directory directory /no_dir_exists does not exist on filesystem',
                'targets list should not be empty',
                'No such file or directory: /no_file_exists'
            }
            assert set(err.args[0]) - expected_errors == set()

    def test_validate_wrong_private_key_permissions(self):
        runner = ssh.ssh_runner.SSHRunner()
        with tempfile.NamedTemporaryFile() as tmp:
            runner.ssh_key_path = tmp.name
            runner.log_directory = '/tmp'
            runner.ssh_user = 'ubuntu'
            runner.targets = ['127.0.0.1']
            os.chmod(tmp.name, 511)  # oct(511) = 0o777
            errors = runner.validate(throw_if_errors=False)
            expected_errors = {
                'permissions 0777 for {} are too open'.format(tmp.name)
            }
            assert set(errors) - expected_errors == set()

    def test_validate(self):
        runner = ssh.ssh_runner.SSHRunner()
        with tempfile.NamedTemporaryFile() as tmp:
            runner.ssh_key_path = tmp.name
            runner.log_directory = '/tmp'
            runner.ssh_user = 'ubuntu'
            runner.targets = ['127.0.0.1']
            os.chmod(tmp.name, 256)  # oct(256) = 0o0400
            runner.validate()


class TestValidate(unittest.TestCase):
    def test_is_valid_ipv4_address(self):
        assert ssh.validate.is_valid_ipv4_address('127.0.0.1') is True
        assert ssh.validate.is_valid_ipv4_address('255.255.255.256') is False
        assert ssh.validate.is_valid_ipv4_address('foo') is False


if __name__ == '__main__':
    unittest.main()
