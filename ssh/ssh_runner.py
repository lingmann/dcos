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
import pty
import subprocess
import warnings
from multiprocessing import Pool

import ssh.helpers
import ssh.validate
from ssh.exceptions import CmdRunException
from ssh.utils import CommandChain, JsonDelegate

log = logging.getLogger(__name__)


def deprecated(func):
    '''This is a decorator which can be used to mark functions
    as deprecated. It will result in a warning being emitted
    when the function is used.'''
    def new_func(*args, **kwargs):
        warnings.warn("Call to deprecated function {}.".format(func.__name__),
                      category=DeprecationWarning)
        return func(*args, **kwargs)
    new_func.__name__ = func.__name__
    new_func.__doc__ = func.__doc__
    new_func.__dict__.update(func.__dict__)
    return new_func


def parse_ip(ip):
    assert isinstance(ip, str), 'IP should be string, {} given'.format(ip)
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
    log.debug('EXECUTING ON {}\n         COMMAND: {}\n'.format(host.ip, ' '.join(cmd)))
    if env is None:
        env = os.environ
    env['TERM'] = 'linux'
    _, slave_pty = pty.openpty()
    process = subprocess.Popen(cmd, stdin=slave_pty, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
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
        "host": {'ip': host.ip, 'port': host.port},
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


class Node():
    def __init__(self, host, tags=None):
        if tags:
            assert isinstance(tags, list)
        if not tags:
            tags = []
        self.tags = tags
        self.host = parse_ip(host)
        self.ip = self.host['ip']
        self.port = self.host['port']

    def add_tag(self, tag):
        assert isinstance(tag, dict)
        self.tags.append(tag)

    def remove_tag(self, tag):
        assert isinstance(tag, dict)
        if tag not in self.tags:
            return None
        _index = self.tags.index(tag)
        del self.tags[_index]

    def get_full_host(self):
        _host = self.host.copy()
        _host.update({'tags': self.tags})
        return _host

    def __repr__(self):
        return '{}:{} tags={}'.format(self.ip, self.port, self.tags)


def add_host(target):
    if isinstance(target, Node):
        return target
    return Node(target)


class MultiRunner():
    def __init__(self, targets, async_delegate=None, ssh_user=None, ssh_key_path=None, extra_opts='',
                 process_timeout=120, parallelism=10):
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
        self.async_delegate = async_delegate
        self.__targets = []
        for target in targets:
            self.__targets.append(add_host(target))
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
            '{}{}'.format(port_option, host.port),
            '-i', self.ssh_key_path
            ]
        shared_opts.extend(add_opts)
        return shared_opts

    @deprecated
    def copy(self, local_path, remote_path, remote_to_local=False, recursive=False):
        def build_scp(host):
            copy_command = []
            if recursive:
                copy_command += ['-r']
            remote_full_path = '{}@{}:{}'.format(self.ssh_user, host.ip, remote_path)
            if remote_to_local:
                copy_command += [remote_full_path, local_path]
            else:
                copy_command += [local_path, remote_full_path]
            return self._get_base_args(self.scp_bin, host) + copy_command
        return self.__run_on_hosts(build_scp)

    @deprecated
    def __run_on_hosts(self, cmd_builder):
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

    @deprecated
    def run(self, cmd):
        assert isinstance(cmd, list)

        def build_ssh(host):
            return self._get_base_args(self.ssh_bin, host) + [
                '{}@{}'.format(self.ssh_user, host.ip)] + cmd
        return self.__run_on_hosts(build_ssh)

    @asyncio.coroutine
    def run_cmd_return_dict_async(self, cmd, host, namespace, future):
        _, slave_pty = pty.openpty()
        process = yield from asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=slave_pty,
            env={'TERM': 'linux'})
        stdout = b''
        stderr = b''
        try:
            stdout, stderr = yield from asyncio.wait_for(process.communicate(), self.process_timeout)
        except asyncio.TimeoutError:
            try:
                process.terminate()
            except ProcessLookupError:
                log.info('process with pid {} not found'.format(process.pid))
            log.error('timeout of {} sec reached. PID {} killed'.format(self.process_timeout, process.pid))

        process_output = {
            '{}:{}'.format(host.ip, host.port): {
                "cmd": cmd,
                "stdout": stdout.decode().split('\n'),
                "stderr": stderr.decode().split('\n'),
                "returncode": process.returncode,
                "pid": process.pid
            }
        }

        future.set_result((namespace, process_output, host))
        return process_output

    @asyncio.coroutine
    def run_async(self, host, command, namespace, future):
        # command consists of (command_flag, command, rollback, comment)
        # we will ignore all but command for now
        _, cmd, _, _ = command
        full_cmd = self._get_base_args(self.ssh_bin, host) + ['{}@{}'.format(self.ssh_user, host.ip)] + cmd
        log.debug('executing command {}'.format(full_cmd))
        result = yield from self.run_cmd_return_dict_async(full_cmd, host, namespace, future)
        return result

    @asyncio.coroutine
    def copy_async(self, host, command, namespace, future):
        # command[0] is command_flag, command[-1] is comment
        # we will ignore them here.
        _, local_path, remote_path, remote_to_local, recursive, _ = command
        copy_command = []
        if recursive:
            copy_command += ['-r']
        remote_full_path = '{}@{}:{}'.format(self.ssh_user, host.ip, remote_path)
        if remote_to_local:
            copy_command += [remote_full_path, local_path]
        else:
            copy_command += [local_path, remote_full_path]
        full_cmd = self._get_base_args(self.scp_bin, host) + copy_command
        log.debug('copy with command {}'.format(full_cmd))
        result = yield from self.run_cmd_return_dict_async(full_cmd, host, namespace, future)
        return result

    def _run_chain_command(self, chain, host, chain_result):
        assert isinstance(chain, CommandChain)
        host_status = 'hosts_success'
        host_port = '{}:{}'.format(host.ip, host.port)

        command_map = {
            CommandChain.execute_flag: self.run_async,
            CommandChain.copy_flag: self.copy_async
        }

        process_exit_code_map = {
            None: {
                'host_status': 'terminated',
                'host_status_count': 'hosts_terminated'
            },
            0: {
                'host_status': 'success',
                'host_status_count': 'hosts_success'
            },
            'failed': {
                'host_status': 'failed',
                'host_status_count': 'hosts_failed'
            }
        }
        for command in chain.get_commands():
            # command[-1] stands for comment
            if command[-1] is not None:
                log.debug('{}: {}'.format(host_port, command[-1]))
            future = asyncio.Future()

            if self.async_delegate is not None:
                log.debug('Using async_delegate with callback')
                callback_called = asyncio.Future()
                future.add_done_callback(lambda future: self.async_delegate.on_update(future, callback_called))

            # command[0] is a type of a command, could be CommandChain.execute_flag, CommandChain.copy_flag
            result = yield from command_map.get(command[0], None)(host, command, chain.namespace, future)
            status = process_exit_code_map.get(result[host_port]['returncode'], process_exit_code_map['failed'])
            host_status = status['host_status']

            if self.async_delegate is not None:
                # We need to make sure the callback was executed before we can proceed further
                # 5 seconds should be enough for a callback.
                try:
                    yield from asyncio.wait_for(callback_called, 5)
                except asyncio.TimeoutError:
                    log.error('Callback did not execute within 5 sec')
                    host_status = 'terminated'
                    break

            _, result, host_object = future.result()
            chain_result.append(result)
            if host_status != 'success':
                break

        if self.async_delegate is not None:
            # Update chain status
            self.async_delegate.on_done(chain.namespace, result, host_object, host_status=host_status)

    @asyncio.coroutine
    def dispatch_chain(self, host, chains, sem):
        log.debug('Started dispatch_chain for host {}'.format(host))
        chain_result = []
        with (yield from sem):
            for chain in chains:
                yield from self._run_chain_command(chain, host, chain_result)
        return chain_result

    @asyncio.coroutine
    def run_commands_chain_async(self, chains, block=False, state_json_dir=None):
        assert isinstance(chains, list)
        sem = asyncio.Semaphore(self.__parallelism)
        if self.async_delegate is not None and state_json_dir is True:
            log.error('Cannot use a delegate and update json at the same time')
            return None
        elif state_json_dir:
            log.debug('Using state_json_dir {}'.format(state_json_dir))
            self.async_delegate = JsonDelegate(state_json_dir, len(self.__targets))

        if block:
            log.debug('Waiting for run_command_chain_async to execute')
            tasks = []
            for host in self.__targets:
                tasks.append(asyncio.async(self.dispatch_chain(host, chains, sem)))

            yield from asyncio.wait(tasks)
            log.debug('run_command_chain_async executed')
            return [task.result() for task in tasks]
        else:
            log.debug('Started run_command_chain_async in non-blocking mode')
            for host in self.__targets:
                asyncio.async(self.dispatch_chain(host, chains, sem))


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
