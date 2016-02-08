import abc
import datetime
import json
import logging
import os
from threading import Timer

from ssh.exceptions import ExecuteException

log = logging.getLogger(__name__)


def handle_command(command):
    '''
    A wrapper, checks command output.
    :param command:
    :raises: ExecuteException if command return code != 0
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
        self.commands_stack = []
        self.namespace = namespace

    def add_execute(self, cmd, rollback=None, comment=None):
        assert isinstance(cmd, list)
        self.commands_stack.append((self.execute_flag, cmd, rollback, comment))

    def add_copy(self, local_path, remote_path, remote_to_local=False, recursive=False, comment=None):
        self.commands_stack.append((self.copy_flag, local_path, remote_path, remote_to_local, recursive, comment))

    def get_commands(self):
        # Return all commands
        return self.commands_stack

    def prepend_command(self, cmd, rollback=None, comment=None):
        # We can specify a command to be executed before the main chain of commands, for example some setup commands
        assert isinstance(cmd, list)
        self.commands_stack.insert(0, (self.execute_flag, cmd, rollback, comment))


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
    def __init__(self, state_dir, targets_len, total_hosts=None, total_masters=None, total_agents=None, **kwargs):
        self.state_dir = state_dir
        self.total_hosts = total_hosts if total_hosts else targets_len
        self.total_masters = total_masters
        self.total_agents = total_agents

    def _update_chain_props(self, status_json, name):
        # Update chain properties. We may update the properties
        if 'hosts' not in status_json:
            status_json['hosts'] = {}

        # Use this hack to update number of total hosts/masters/agent on the fly. This is used on deploy 'retry'.
        if status_json.get('total_hosts') != self.total_hosts:
            status_json['total_hosts'] = self.total_hosts

        if status_json.get('total_masters') != self.total_masters:
            status_json['total_masters'] = self.total_masters

        if status_json.get('total_agents') != self.total_agents:
            status_json['total_agents'] = self.total_agents

        status_json['chain_name'] = name

    def _read_json_state(self, name):
        status_file = os.path.join(self.state_dir, '{}.json'.format(name))
        if os.path.isfile(status_file):
            with open(status_file) as f:
                return json.load(f)
        return {}

    def _dump_json_state(self, name, status_json):
        status_file = os.path.join(self.state_dir, '{}.json'.format(name))

        with open(status_file, 'w') as f:
            try:
                json.dump(status_json, f)
            except IOError:
                log.error('Could not update state file {}'.format(status_file))

    def on_update(self, future, callback_called):
        self._update_json_file(*future.result(), future_update=True, callback_called=callback_called)

    def on_done(self, name, result, host_status=None):
        self._update_json_file(name, result, None, host_status=host_status)

    def _update_json_file(self, name, result, host_object, future_update=None, host_status=None, callback_called=None):
        status_json = self._read_json_state(name)
        self._update_chain_props(status_json, name)

        for host, return_values in result.items():
            # Block is executed for on_update callback
            if future_update:
                return_values.update({
                    'date': str(datetime.datetime.now())
                })

                # Append to commands
                if host in status_json['hosts']:
                    status_json['hosts'][host]['commands'].append(return_values)
                else:
                    status_json['hosts'][host] = {
                        'commands': [return_values]
                    }

                if host_object.tags and 'tags' not in status_json['hosts'][host]:
                    status_json['hosts'][host]['tags'] = {}
                    for tag in host_object.tags:
                        status_json['hosts'][host]['tags'].update(tag)

                # Update chain status to running if not other state found.
                if 'host_status' not in status_json['hosts'][host]:
                    status_json['hosts'][host]['host_status'] = 'running'

        # Update chain status: success or fail
        if host_status:
            status_json['hosts'][host]['host_status'] = host_status

        self._dump_json_state(name, status_json)
        if callback_called:
                callback_called.set_result(True)


def set_timer(state_dir, interval=10, invoke_func=None):
    assert os.path.isdir(state_dir), 'state_dir should be a path to dump state files'
    t = Timer(interval, invoke_func)
    t.start()
    return t


class MemoryDelegate(JsonDelegate):
    """
    MemoryDelegate reuses JsonDelegate logic, overriding save/load logic
    A state is stored self.state['chain_name']
    """
    def __init__(self, total_hosts=None, total_masters=None, total_agents=None, state_dir=None,
                 trigger_states_func=set_timer):
        self.total_hosts = total_hosts
        self.total_agents = total_agents
        self.total_masters = total_masters
        self.state_dir = state_dir
        self.state = {}
        self.trigger_states_func = trigger_states_func
        self.timer = None
        self.set_up_trigger()

    def set_up_trigger(self):
        # If you want to change the default interval simply:
        #
        # from ssh.utils import set_timer
        # md = MemoryDelegate(trigger_states_func=lambda *args, **kwargs: set_timer(*args, interval=1, **kwargs))
        if not self.trigger_states_func:
            log.warning('Json states will not be dumped to a disk.')
            return None

        def funcs():
            self.dump_status_files()
            self.set_up_trigger()

        # Set timer only if user provided a directory to store states.
        if self.state_dir and os.path.isdir(self.state_dir):
            self.timer = self.trigger_states_func(self.state_dir, invoke_func=lambda: funcs())

    def _read_json_state(self, name):
        if name not in self.state:
            self.state[name] = {}
        return self.state.get(name)

    def _dump_json_state(self, name, status_json):
        # Hard copy status_json object
        self.state[name] = status_json.copy()

    def dump_status_files(self):
        if not self.state_dir:
            log.error('Cannot save state files, state_dir should be passed via constructor')
            return False
        for state, state_object in self.state.items():
            with open(os.path.join(self.state_dir, '{}.json'.format(state)), 'w') as fh:
                log.debug('Dumping {} to a dir {}'.format(state, self.state_dir))
                json.dump(state_object, fh)
