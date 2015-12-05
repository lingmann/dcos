import unittest
import unittest.mock

import ssh.ssh_runner


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
        assert self.multirunner.copy_recursive('/tmp/pilot.txt', '/usr') == [
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

    @unittest.mock.patch('ssh.ssh_runner.MultiRunner')
    def test_execute_cmd(self, mocked_multirunner):
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

    @unittest.mock.patch('ssh.helpers.dump_host_results')
    def test_save_log(self, mocked_dump_host_results):
        mock_struct_data = [
            {
                'host': {
                    'ip': '127.0.0.1'
                }
            }
        ]
        self.ssh_runner.save_logs(mock_struct_data)


if __name__ == '__main__':
    unittest.main()
