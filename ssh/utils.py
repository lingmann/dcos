import abc
import json
import logging
import os
from datetime import datetime

from ssh.validate import ExecuteException

log = logging.getLogger(__name__)


def handle_command(command):
    '''
    A wrapper, checks command output.
    :param command:
    :raises: ssh.validate.ExecuteException if command return code != 0
    '''
    failed = []
    for output in command():
        if output['stdout']:
            log.info('\n'.join(output['stdout']))
        if output['returncode'] != 0:
            log.error(output)
            failed.append(output)

    if failed:
        raise ExecuteException()


class CommandChain():
    '''
    Add command to execute on a remote host.

    :param cmd: String, command to execute
    :param rollback: String (optional) a rollback command
    :param comment: String (optional)
    :return:
    '''
    execute_flag = 'execute'
    copy_flag = 'copy'

    def __init__(self, namespace):
        self.pre_commands = []
        self.post_commands = []
        self.commands_stack = []
        self.namespace = namespace

    def add_execute(self, cmd, rollback=None, comment=None):
        assert isinstance(cmd, list)
        self.commands_stack.append((self.execute_flag, cmd, rollback, comment))

    def add_copy(self, local_path, remote_path, remote_to_local=False, recursive=False, comment=None):
        self.commands_stack.append((self.copy_flag, local_path, remote_path, remote_to_local, recursive, comment))

    def get_commands(self):
        # Return all commands
        return self.pre_commands + self.commands_stack + self.post_commands

    def prepend_command(self, cmd, rollback=None, comment=None):
        # We can specify a command to be executed before the main chain of commands, for example some setup commands
        assert isinstance(cmd, list)
        self.pre_commands.append((self.execute_flag, cmd, rollback, comment))

    def append_command(self, cmd, rollback=None, comment=None):
        # We can also cleanup commands if needed.
        assert isinstance(cmd, list)
        self.post_commands.append((self.execute_flag, cmd, rollback, comment))


class AbstractSSHLibDelegate(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def on_update(self, future, callback):
        '''
        A method called on update
        :param future: An instance of asyncio.Future() passed by a callback
        :param callback: should run callback.set_result(True) to indicate that callback was successfully executed
        :return:
        '''
        pass

    @abc.abstractmethod
    def on_done(self, name, result, host_status_count=None, host_status=None):
        '''
        A method called when chain execution is finished
        :param name: A unique chain identifier
        :param result: asyncio.Future().result()
        :param host_status_count: String
        :param host_status: String
        :return:
        '''
        pass


class JsonDelegate(AbstractSSHLibDelegate):
    def __init__(self, state_dir, total_hosts, tags=None):
        self.state_dir = state_dir
        self.total_hosts = total_hosts
        self.tags = tags

    def on_update(self, future, callback_called):
        self._update_json_file(*future.result(), future_update=True, callback_called=callback_called)

    def on_done(self, name, result, host_status_count=None, host_status=None):
        self._update_json_file(name, result, host_status_count=host_status_count, host_status=host_status)

    def _update_json_file(self, name, result, future_update=None, host_status_count=None, host_status=None,
                          callback_called=None):
        status_json = {}
        status_file = os.path.join(self.state_dir, '{}.json'.format(name))
        if os.path.isfile(status_file):
            with open(status_file) as f:
                status_json = json.load(f)

        for host, return_values in result.items():
            if future_update:
                return_values.update({
                    'date': str(datetime.now())
                })

                # Append to commands
                if host in status_json:
                    status_json[host]['commands'].append(return_values)
                else:
                    # Create a new chain properties
                    status_json['total_hosts'] = self.total_hosts
                    status_json['chain_name'] = name
                    status_json[host] = {
                        'commands': [return_values]
                    }

                if self.tags and 'tags' not in status_json[host]:
                    status_json[host]['tags'] = {}
                    for tag in self.tags:
                        status_json[host]['tags'].update(tag)

                # Update chain status to running
                if 'host_status' not in status_json[host]:
                    status_json[host]['host_status'] = 'running'

            # Update chain status: success or fail
            if host_status:
                status_json[host]['host_status'] = host_status

            if host_status_count:
                status_json[host_status_count] = status_json.get(host_status_count, 0) + 1

        with open(status_file, 'w') as f:
            json.dump(status_json, f)

        if callback_called:
                callback_called.set_result(True)
