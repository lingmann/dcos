"""Python API for interacting with installer API
"""
import abc
import json
import os
import stat
import subprocess
from contextlib import contextmanager

import requests
import yaml
from retrying import retry


class AbstractDcosInstaller(metaclass=abc.ABCMeta):
    def get_hashed_password(self, password):
        p = subprocess.Popen(
                ["bash", self.installer_path, "--hash-password", password],
                stderr=subprocess.PIPE)
        return p.communicate()[1].decode('utf-8').split("\n")[-2].strip('\x1b[0m')

    @abc.abstractmethod
    def genconf(self, expect_errors=False):
        pass

    @abc.abstractmethod
    def preflight(self, expect_errors=False):
        pass

    @abc.abstractmethod
    def install_prereqs(self, expect_errors=False):
        pass

    @abc.abstractmethod
    def deploy(self, expect_errors=False):
        pass

    @abc.abstractmethod
    def postflight(self, expect_errors=False):
        pass


class DcosApiInstaller(AbstractDcosInstaller):
    def __init__(self, port=9000, installer_path=None):
        assert os.path.isfile(installer_path), "Not a file: {}".format(installer_path)
        self.url = "http://0.0.0.0:{}".format(port)
        self.installer_path = installer_path
        self.process_handler = None
        self.timeout = 900
        self.offline_mode = False

    @contextmanager
    def run_web_server(self):
        @retry(wait_fixed=1000, stop_max_delay=10000)
        def wait_for_up():
            assert requests.get(self.url).status_code == 200
            print("Webserver started")

        cmd = ["bash", self.installer_path, "--web"]
        if self.offline_mode:
            cmd.append('--offline')
        p = subprocess.Popen(cmd)
        assert p.poll() is None, "Webserver failed to start!"
        wait_for_up()
        yield
        print("Stopping installer...")

        @retry(wait_fixed=1000)
        def wait_for_death():
            p.terminate()
            assert p.poll() is not None

        wait_for_death()

    def genconf(
            self, master_list, agent_list, ssh_user, zk_host, ssh_key,
            ip_detect_script, superuser=None, su_passwd=None, expect_errors=False):
        """Runs configuration generation.

        Args:
            master_list: list of IPv4 addresses to be used as masters
            agent_list: list of IPv4 addresses to be used as agents
            zk_host (str): host and port for bootstrap ZK
            ip_detect_script (str): complete contents of IP-detect script
            ssh_user (str): name of SSH user that has access to targets
            ssh_key (str): complete public SSH key for ssh_user. Must already
                be installed on tagets as authorized_key
            expect_errors (optional): raises error if result is unexpected

        Raises:
            AssertionError: "error" present in returned json keys when error
                was not expected or vice versa
        """
        with self.run_web_server():
            headers = {'content-type': 'application/json'}
            payload = {
                "master_list": master_list,
                "agent_list": agent_list,
                "ssh_user": ssh_user,
                "exhibitor_zk_hosts": zk_host,
                "ssh_key": ssh_key,
                'ip_detect_script': ip_detect_script}
            if superuser:
                payload["superuser_username"] = superuser
            if su_passwd:
                payload["superuser_password_hash"] = su_passwd
            response = requests.post(self.url + '/api/v1/configure', headers=headers, data=json.dumps(payload))
            assert response.status_code == 200
            response_json_keys = list(response.json().keys())
            if expect_errors:
                assert "error" in response_json_keys
            else:
                assert "error" not in response_json_keys

    def install_prereqs(self, expect_errors=False):
        assert not self.offline_mode, "Install prereqs can only be run without --offline mode"
        self.preflight(expect_errors=expect_errors)

    def preflight(self, expect_errors=False):
        self.do_and_check('preflight', expect_errors)

    def deploy(self, expect_errors=False):
        self.do_and_check('deploy', expect_errors)

    def postflight(self, expect_errors=False):
        self.do_and_check('postflight', expect_errors)

    def do_and_check(self, action, expect_errors):
        """Args:
            action (str): one of 'preflight', 'deploy', 'postflight'
        """
        with self.run_web_server():
            self.start_action(action)
            self.wait_for_check_action(
                action=action, expect_errors=expect_errors,
                wait=30000, stop_max_delay=900*1000)

    def wait_for_check_action(self, action, wait, stop_max_delay, expect_errors):
        """Retries method against API until returned data shows that all hosts
        have finished.

        Args:
            action (str): choies are 'preflight', 'deploy', 'postflight'
            wait (int): how many milliseconds to wait between tries
            stop_max_delay (int): total duration (in milliseconds) to retry for
            expect_errors (boolean): raises error if result is not as expected

        Raises:
            AssertionError: checks 'host_status' and raises error...
                -if expect_errors is False and not all status=='success'
                -if expect_errors is True and all status=='success'
        """
        @retry(wait_fixed=wait, stop_max_delay=stop_max_delay)
        def wait_for_finish():
            # Only return if output is not empty and all hosts are not running
            output = self.check_action(action)
            assert output != {}
            host_data = output['hosts']
            assert all(map(lambda host: host['host_status'] != 'running', host_data.values()))
            return host_data

        host_data = wait_for_finish()
        success = True
        for host in host_data.keys():
            if host_data[host]['host_status'] != 'success':
                success = False
                print("Failures detected in {}: {}".format(action, host_data[host]))
        if expect_errors:
            assert not success, "Results were successful, but errors were expected in {}".format(action)
        else:
            assert success, "Results for {} included failures, when all should have succeeded".format(action)

    def start_action(self, action):
        """Args:
            action (str): one of 'preflight', 'deploy', 'postflight'
        """
        return requests.post(self.url + '/api/v1/action/{}'.format(action))

    def check_action(self, action):
        """Args:
            action (str): one of 'preflight', 'deploy', 'postflight', 'success'
        """
        return requests.get(self.url + '/api/v1/action/{}'.format(action)).json()


class DcosCliInstaller(AbstractDcosInstaller):
    def __init__(self, installer_path=None):
        assert os.path.isfile(installer_path), "Not a file: {}".format(installer_path)
        self.installer_path = installer_path

    def run_cli_cmd(self, mode, expect_errors=False):
        """Runs commands through the CLI
        NOTE: We use `bash` as a wrapper here to make it so dcos_generate_config.sh
        doesn't have to be executable

        Args:
            mode (str): single flag to be handed to CLI
            expect_errors: raise error if result is unexpected

        Raises:
            AssertionError: if return_code is...
                -zero and expect_errors is True
                -nonzero and expect_errors is False
        """
        cmd = ['bash', self.installer_path, mode]
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out = p.communicate()[1].decode()
        if expect_errors:
            err_msg = "{} exited with error code {} (success), but expected an error.\nOutput: {}"
            assert p.returncode != 0, err_msg.format(mode, p.returncode, out)
        else:
            err_msg = "{} exited with error code {}.\nOutput: {}"
            assert p.returncode == 0, err_msg.format(mode, p.returncode, out)

    def genconf(
            self, master_list, agent_list, ssh_user, zk_host, ssh_key,
            ip_detect_script, superuser=None, su_passwd=None, expect_errors=False):
        """Runs configuration generation.

        Args:
            master_list: list of IPv4 addresses to be used as masters
            agent_list: list of IPv4 addresses to be used as agents
            zk_host (str): host and port for bootstrap ZK
            ip_detect_script (str): complete contents of IP-detect script
            ssh_user (str): name of SSH user that has access to targets
            ssh_key (str): complete public SSH key for ssh_user. Must already
                be installed on tagets as authorized_key
            expect_errors (optional): raises error if result is unexpected
            sy

        Raises:
            AssertionError: "error" present in returned json keys when error
                was not expected or vice versa
        """

        test_config = {
            'cluster_name': 'SSH Installed DCOS',
            'bootstrap_url': 'file:///opt/dcos_install_tmp',
            'dns_search': 'mesos',
            'exhibitor_storage_backend': 'zookeeper',
            'exhibitor_zk_hosts': zk_host,
            'exhibitor_zk_path': '/exhibitor',
            'master_discovery': 'static',
            'master_list': master_list,
            'ssh_user': ssh_user,
            'agent_list': agent_list,
            'process_timeout': 900}
        if superuser:
            test_config['superuser_username'] = superuser
        if su_passwd:
            test_config['superuser_password_hash'] = su_passwd
        with open('genconf/config.yaml', 'w') as config_fh:
            config_fh.write(yaml.dump(test_config))
        with open('genconf/ip-detect', 'w') as ip_detect_fh:
            ip_detect_fh.write(ip_detect_script)
        with open('genconf/ssh_key', 'w') as key_fh:
            key_fh.write(ssh_key)
        os.chmod("genconf/ssh_key", stat.S_IREAD | stat.S_IWRITE)
        self.run_cli_cmd('--genconf', expect_errors=expect_errors)

    def preflight(self, expect_errors=False):
        self.run_cli_cmd('--preflight', expect_errors=expect_errors)

    def install_prereqs(self, expect_errors=False):
        self.run_cli_cmd('--install-prereqs', expect_errors=expect_errors)
        self.preflight()

    def deploy(self, expect_errors=False):
        self.run_cli_cmd('--deploy', expect_errors=expect_errors)

    def postflight(self, expect_errors=False):
        self.run_cli_cmd('--postflight', expect_errors=expect_errors)
