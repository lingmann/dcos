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
import asyncio
import json
import logging
import os
import subprocess
from multiprocessing import Pool

import ssh.helpers
import ssh.validate

log = logging.getLogger(__name__)


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


def run_cmd_return_tuple(host, cmd, timeout_sec=120, env=None, ignore_warning=True):
    '''
    Run a shell command
    :param host: Dict, {'ip': '127.0.0.1, 'port': 22}
    :param cmd: List, shell command in the following format ['ls', '-la']
    :param timeout: Integer, a timeout to run a command in seconds
    :param env: Dict, environment variables os.environ
    :return: Dict in the following format:
            {
              'cmd': ['ls', '-la'],
              'host': '10.10.10.1',
              'stdout': 'some stdout\nwith new line\n',
              'stderr': 'some stderr\nwith new line\n',
              'returncode': 0,
              'pid': 123
            }
    '''
    log.debug('EXECUTING ON {}\n         COMMAND: {}\n'.format(host['ip'], ' '.join(cmd)))
    if env is None:
        env = os.environ

    process = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    stdout, stderr = process.communicate(timeout=timeout_sec)

    if ignore_warning and isinstance(stderr, bytes):
        # For each possible line in stderr, match from the beginning of the line for the
        # the confusing warning: "Warning: Permanently added ...". If the warning exists,
        # remove it from the string when ignore_warning is True (default).
        err_arry = stderr.decode().split('\r')
        # Re-cast to bytes since we may pass False to ignore_warning,
        # in which case we need to ensure to run decode().
        stderr = bytes('\n'.join([line for line in err_arry if not line.startswith(
            'Warning: Permanently added')]), 'utf-8')

    return {
        "cmd": cmd,
        "host": host,
        "stdout": stdout.decode().split('\n'),
        "stderr": stderr.decode().split('\n'),
        "returncode": process.returncode,
        "pid": process.pid
    }


def save_logs(results, log_directory, log_postfix):
    try:
        index = 0
        for result in results:
            host = result['host']['ip']
            ssh.helpers.dump_host_results(
                log_directory,
                host,
                ssh.helpers.get_structured_results(result, index),
                log_postfix)
            index += 1
    except IOError:
        pass
    return results


class CommandsChain():
    '''
    A chain of commands to execute
    '''
    execute_flag = 'execute'
    copy_flag = 'copy'

    def __init__(self, namespace):
        self.commands_stack = []
        self.namespace = namespace

    def add_execute_cmd(self, cmd, rollback=None, comment=None):
        '''
        Add command to execute on a remote host.

        :param cmd: String, command to execute
        :param rollback: String (optional) a rollback command
        :param comment: String (optional)
        :return:
        '''
        cmd = cmd.split()
        self.commands_stack.append((self.execute_flag, cmd, rollback, comment))

    def add_copy_cmd(self, local_path, remote_path, remote_to_local=False, recursive=False, comment=None):
        self.commands_stack.append((self.copy_flag, local_path, remote_path, remote_to_local, recursive, comment))

    def get_commands(self):
        return self.commands_stack


class MultiRunner():
    def __init__(self, targets, state_dir=None, ssh_user=None, ssh_key_path=None, extra_opts='', process_timeout=120,
                 parallelism=10):
        assert isinstance(targets, list)
        # TODO(cmaloney): accept an "ssh_config" object which generates an ssh
        # config file, then add a '-F' to that temporary config file rather than
        # manually building up / adding the arguments in _get_base_args which is
        # very error prone to get the formatting right. Should have just one
        # host section which applies to all hosts, sets things like "user".
        self.extra_opts = extra_opts
        self.process_timeout = process_timeout
        self.ssh_user = ssh_user
        self.ssh_key_path = ssh_key_path
        self.ssh_bin = '/usr/bin/ssh'
        self.scp_bin = '/usr/bin/scp'
        self.state_dir = state_dir
        self.__targets = [parse_ip(ip) for ip in targets]
        self.__parallelism = parallelism

    def _get_base_args(self, bin_name, host):
        # TODO(cmaloney): Switch to SSH config file, documented above. A single
        # user is always required.
        if bin_name == self.ssh_bin:
            port_option = '-p'
            add_opts = ['-tt']
            if self.extra_opts:
                add_opts.extend(self.extra_opts.split(' '))
        else:
            port_option = '-P'
            add_opts = []
        shared_opts = [
            bin_name,
            '-oConnectTimeout=10',
            '-oStrictHostKeyChecking=no',
            '-oUserKnownHostsFile=/dev/null',
            '-oBatchMode=yes',
            '-oPasswordAuthentication=no',
            '{}{}'.format(port_option, host['port']),
            '-i', self.ssh_key_path
            ]
        shared_opts.extend(add_opts)
        return shared_opts

    def copy(self, local_path, remote_path, remote_to_local=False, recursive=False):
        '''Deprecated'''
        def build_scp(host):
            copy_command = []
            if recursive:
                copy_command += ['-r']
            remote_full_path = '{}@{}:{}'.format(self.ssh_user, host['ip'], remote_path)
            if remote_to_local:
                copy_command += [remote_full_path, local_path]
            else:
                copy_command += [local_path, remote_full_path]
            return self._get_base_args(self.scp_bin, host) + copy_command
        return self.__run_on_hosts(build_scp)

    def __run_on_hosts(self, cmd_builder):
        '''Deprecated'''
        host_cmd_tuples = [(host, cmd_builder(host), self.process_timeout) for host in self.__targets]

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
        '''Deprecated'''
        assert isinstance(cmd, list)

        def build_ssh(host):
            return self._get_base_args(self.ssh_bin, host) + [
                '{}@{}'.format(self.ssh_user, host['ip'])] + cmd
        return self.__run_on_hosts(build_ssh)

    @asyncio.coroutine
    def run_cmd_return_dict_async(self, cmd, host, namespace, future):
        process = yield from asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE,
                                                            stderr=asyncio.subprocess.PIPE,
                                                            stdin=asyncio.subprocess.DEVNULL)

        stdout = yield from process.stdout.read()
        stderr = yield from process.stderr.read()
        yield from process.wait()

        process_output = {
            '{}:{}'.format(host['ip'], host['port']): {
                "cmd": cmd,
                "stdout": stdout.decode().split('\n'),
                "stderr": stderr.decode().split('\n'),
                "returncode": process.returncode,
                "pid": process.pid
            }
        }

        if self.state_dir is not None:
            future.set_result((namespace, process_output))
        return process_output

    @asyncio.coroutine
    def run_async(self, host, command, namespace, future):
        _, cmd, rollback, comment = command
        full_cmd = self._get_base_args(self.ssh_bin, host) + ['{}@{}'.format(self.ssh_user, host['ip'])] + cmd
        result = yield from self.run_cmd_return_dict_async(full_cmd, host, namespace, future)
        return result

    @asyncio.coroutine
    def copy_async(self, host, command, namespace, future):
        print('Called copy_async for {} with command {}'.format(host, command))

    def update_json(self, future):
        print('This is future')
        self._update_json_file(*future.result(), future_update=True)

    def _update_json_file(self, namespace, process_output, future_update=None, chain_status=None, status_dict=None):
        status_json = {}
        status_file = os.path.join(self.state_dir, '{}.json'.format(namespace))
        if os.path.isfile(status_file):
            with open(status_file) as f:
                status_json = json.load(f)

        for host, return_values in process_output.items():
            if future_update:
                if host in status_json:
                    status_json[host]['commands'].append(return_values)
                else:
                    status_json[host] = {
                        'commands': [return_values]
                    }

            # Update chain status: success or fail
            if chain_status:
                status_json[host]['chain_status'] = chain_status

            if status_dict:
                assert isinstance(status_dict, dict)
                status_json.update(status_dict)

        with open(status_file, 'w') as f:
            json.dump(status_json, f)

    @asyncio.coroutine
    def dispatch_command(self, host, chain, sem):
        with (yield from sem):
            chain_status = 'success'
            for command in chain.get_commands():
                future = asyncio.Future()
                future.add_done_callback(self.update_json)

                command_type = command[0]
                if command_type == CommandsChain.execute_flag:
                    result = yield from self.run_async(host, command, chain.namespace, future)
                elif command_type == CommandsChain.copy_flag:
                    result = yield from self.copy_async(host, command, chain.namespace, future)
                else:
                    raise NotImplementedError(command_type)

                # example: result['127.0.0.1:22022']['returncode']
                # TODO(mnaboka): add rollback logic here
                if result['{}:{}'.format(host['ip'], host['port'])]['returncode'] != 0:
                    chain_status = 'failed'
                    break

            self._update_json_file(chain.namespace, result, chain_status=chain_status)

    @asyncio.coroutine
    def run_commands_chain_async(self, chain):
        assert isinstance(chain, CommandsChain)

        sem = asyncio.Semaphore(self.__parallelism)
        tasks = []
        for host in self.__targets:
            tasks.append(asyncio.async(self.dispatch_command(host, chain, sem)))
        yield from asyncio.wait(tasks)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    mr = MultiRunner(['127.0.0.1:22022'], ssh_user='mnaboka', ssh_key_path='/Users/mnaboka/.ssh/id_rsa',
                     state_dir='/tmp')
    chain = CommandsChain('preflight')
    chain.add_execute_cmd('uname -a')
    chain.add_execute_cmd('uname -a')

    try:
        loop.run_until_complete(mr.run_commands_chain_async(chain))
    finally:
        loop.close()


tuple_to_string_header = """HOST: {}
COMMAND: {}
RETURNCODE: {}
PID: {}
"""


def cmd_tuple_to_string(cmd_tuple):
    """Transforms the given tuple returned from run_cmd_return_tuple into a user-friendly string message"""
    string = tuple_to_string_header.format(
        cmd_tuple['host'],
        " ".join(cmd_tuple['cmd']),
        cmd_tuple['returncode'],
        cmd_tuple['pid'])

    if cmd_tuple['stdout']:
        string += "STDOUT:\n" + '\n'.join(cmd_tuple['stdout'])
    if cmd_tuple['stderr']:
        string += "STDERR:\n" + '\n'.join(cmd_tuple['stderr'])

    return string


class CmdRunException(Exception):

    def __init__(self, results):
        message = "\n".join(map(cmd_tuple_to_string, results))
        super(CmdRunException, self).__init__(message)
        self.results = results


class SSHRunner():
    def __init__(self, use_cache=False):
        self.extra_ssh_options = ''
        self.ssh_key_path = None
        self.ssh_user = None
        self.targets = []
        self.log_directory = None
        self.use_cache = use_cache
        self.__cache_file = './.cache.json'
        self.log_postfix = 'ssh_data'
        self.process_timeout = 120

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
        results = dump_success_hosts(eval_command())
        save_logs(results, self.log_directory, self.log_postfix)
        return results

    def validate(self, throw_if_errors=True):
        with ssh.validate.ErrorsCollector(throw_if_errors=throw_if_errors) as ec:
            ec.is_not_none(self, [
                'log_directory',
                'ssh_user',
                'process_timeout',
                'ssh_key_path'
            ])

            ec.is_string(self, [
                'log_directory',
                'ssh_user',
                'log_postfix',
                'extra_ssh_options',
                'ssh_key_path'
            ])

            ec.is_file(self, [
                'ssh_key_path'
            ])

            ec.is_dir(self, [
                'log_directory'
            ])

            ec.is_list_not_empty(self, [
                'targets'
            ])

            ec.is_valid_ip(self, [
                'targets'
            ])

            ec.is_valid_private_key_permission(self, [
                'ssh_key_path'
            ])
            return ec.validate()

    def execute_cmd(self, cmd, throw_on_error=False):
        self.validate()
        runner = MultiRunner(
            self.exclude_cached(self.targets),
            ssh_user=self.ssh_user,
            ssh_key_path=self.ssh_key_path,
            extra_opts=self.extra_ssh_options,
            process_timeout=self.process_timeout)

        results = self.wrapped_run(lambda: runner.run(cmd.split()))

        if throw_on_error:
            # If any results exited with non-zero, throw an exception with results attached
            error_exits = list(filter(lambda result: result['returncode'] != 0, results))

            if len(error_exits) > 0:
                raise CmdRunException(error_exits)

        return results

    def exclude_cached(self, hosts):
        if not self.use_cache or not os.path.isfile(self.__cache_file):
            return hosts
        try:
            with open(self.__cache_file) as fh:
                dump = json.load(fh)
        except IOError:
            return hosts
        return list(filter(lambda x: x not in dump['success_hosts'], hosts))

    def copy_cmd(self, local_path, remote_path, recursive=False, remote_to_local=False):
        self.validate()
        runner = MultiRunner(self.exclude_cached(self.targets),
                             ssh_user=self.ssh_user,
                             ssh_key_path=self.ssh_key_path,
                             process_timeout=self.process_timeout)
        return self.wrapped_run(lambda: runner.copy(local_path, remote_path, remote_to_local=remote_to_local,
                                                    recursive=recursive))
