"""
preflight = SSHRunner()
preflight.ssh_user = 'ubuntu'
preflight.ssh_key_path = '/home/ubuntu/key.pem'
preflight.targets = ['127.0.0.1', '127.0.0.2']
preflight.log_directory = '/tmp'
preflight.use_cache = False

preflight.execute_cmd(cmd)

preflight.copy_cmd('/tmp/file.txt', '/tmp')
preflight.copy_cmd('/usr', '/', recursive=True)
"""
import subprocess
from multiprocessing import Pool
import ssh.helpers
import json
import os


def parse_ip(ip):
    tmp = ip.split(':')
    if len(tmp) == 2:
        return {"ip": tmp[0], "port": int(tmp[1])}
    elif len(tmp) == 1:
        return {"ip": ip, "port": 22}
    else:
        raise ValueError(
            "Expected a string of form <ip> or <ip>:<port> but found a string with more than one " +
            "colon in it. NOTE: IPv6 is not supported at this time. Got: {}".format(ip))


def run_cmd_return_tuple(host, cmd):
    print(cmd)
    exec = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = exec.communicate()
    return {
        "cmd": cmd,
        "host": host,
        "stdout": stdout.decode().split('\n'),
        "stderr": stderr.decode().split('\n'),
        "returncode": exec.returncode,
        "pid": exec.pid
    }


class MultiRunner():
    def __init__(self, targets, ssh_user=None, ssh_key_path=None, parallelism=10):
        assert isinstance(targets, list)
        # TODO(cmaloney): accept an "ssh_config" object which generates an ssh
        # config file, then add a '-F' to that temporary config file rather than
        # manually building up / adding the arguments in _get_base_args which is
        # very error prone to get the formatting right. Should have just one
        # host section which applies to all hosts, sets things like "user".
        self.ssh_user = ssh_user
        self.ssh_key_path = ssh_key_path
        self.ssh_bin = '/usr/bin/ssh'
        self.scp_bin = '/usr/bin/scp'
        self.__targets = [parse_ip(ip) for ip in targets]
        self.__parallelism = parallelism

    def _get_base_args(self, bin_name, host):
        # TODO(cmaloney): Switch to SSH config file, documented above. A single
        # user is always required.
        port_option = '-p' if bin_name is self.ssh_bin else '-P'
        return [
            bin_name,
            '{}{}'.format(port_option, host['port']),
            '-i', self.ssh_key_path
        ]

    def copy(self, local_path, remote_path):
        def build_scp(host):
            return self._get_base_args(self.scp_bin, host) + [
                local_path,
                '{}@{}:{}'.format(self.ssh_user, host['ip'], remote_path)]
        return self.__run_on_hosts(build_scp)

    def copy_recursive(self, local_dir, remote_dir):
        def build_scp_recursive(host):
            return self._get_base_args(self.scp_bin, host) + [
                '-r',
                local_dir,
                '{}@{}:{}'.format(self.ssh_user, host['ip'], remote_dir)]
        return self.__run_on_hosts(build_scp_recursive)

    def __run_on_hosts(self, cmd_builder):
        host_cmd_tuples = [(host, cmd_builder(host)) for host in self.__targets]

        # NOTE: There are extra processes created here (We should be able to
        # just run N subprocesses at a time and wait for signals from any of n
        # of them in one thread), but this is _really_ simple / straightforwad
        # to implement and handle all possible error cases. Can
        # optimize when it is proven to be necessary.
        with Pool(self.__parallelism) as pool:
            # TODO(cmaloney): Switch to async_starmap and make it so we can
            # report back to the webui as each process completes / fails / etc
            # Rather than just hanging until they all return.
            return pool.starmap(run_cmd_return_tuple, host_cmd_tuples)

    def run(self, cmd):
        assert isinstance(cmd, list)

        def build_ssh(host):
            return self._get_base_args(self.ssh_bin, host) + [
                '{}@{}'.format(self.ssh_user, host['ip'])] + cmd
        return self.__run_on_hosts(build_ssh)


class SSHRunner():
    ssh_key_path = None
    ssh_user = None
    targets = []
    log_directory = None

    def __init__(self, use_cache=False):
        self.use_cache = use_cache
        self.__cache_file = './.cache.json'

    def save_logs(self, results):
        try:
            for result in results:
                host = result['host']['ip']
                ssh.helpers.dump_host_results(self.log_directory, host, ssh.helpers.get_structured_results(result))
        except IOError:
            pass
        return results

    def wrapped_run(self, eval_command):
        def dump_success_hosts(results):
            if self.use_cache:
                success_hosts = []
                for result in results:
                    if result['returncode'] == 0:
                        success_hosts.append(result['host']['ip'])
                dump = {}
                if os.path.isfile(self.__cache_file):
                    with open(self.__cache_file) as fh:
                        dump = json.load(fh)
                dump.setdefault('success_hosts', []).extend(success_hosts)
                with open(self.__cache_file, 'w') as fh:
                    json.dump(dump, fh)
            return results
        return self.save_logs(dump_success_hosts(eval_command()))

    def validate(self, fail_on_error=False):
        # TODO(mnaboka): improve validation
        errors = []
        if self.ssh_user is None:
            errors.append('ssh_user must be set')
        if self.ssh_key_path is None:
            errors.append('ssh_key_path must be set')
        if len(self.targets) == 0:
            errors.append('targets must be set')
        if self.log_directory is None:
            errors.append('log_directory must be set')
        if fail_on_error:
            if len(errors) > 0:
                raise ssh.helpers.ValidateException(','.join(errors))
        return errors

    def execute_cmd(self, cmd):
        self.validate(fail_on_error=True)
        runner = MultiRunner(self.exclude_cached(self.targets), ssh_user=self.ssh_user, ssh_key_path=self.ssh_key_path)
        return self.wrapped_run(lambda: runner.run(cmd.split()))

    def exclude_cached(self, hosts):
        if not self.use_cache or not os.path.isfile(self.__cache_file):
            return hosts
        try:
            with open(self.__cache_file) as fh:
                dump = json.load(fh)
        except IOError:
            return hosts
        return list(filter(lambda x: x not in dump['success_hosts'], hosts))

    def copy_cmd(self, local_path, remote_path, recursive=False):
        self.validate(fail_on_error=True)
        runner = MultiRunner(self.exclude_cached(self.targets), ssh_user=self.ssh_user, ssh_key_path=self.ssh_key_path)
        if recursive:
            return self.wrapped_run(lambda: runner.copy_recursive(local_path, remote_path))
        else:
            return self.wrapped_run(lambda: runner.copy(local_path, remote_path))
