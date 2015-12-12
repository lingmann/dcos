import logging

from ssh.validate import ExecuteException

log = logging.getLogger(__name__)


def handle_command(command):
    '''
    A wrapper, checks command output.
    :param command:
    :raises: ssh.validate.ExecuteException if command return code != 0
    '''
    for output in command():
        if output['stdout']:
            log.info('\n'.join(output['stdout']))
        if output['returncode'] != 0:
            log.error(output)
            raise ExecuteException(output)
