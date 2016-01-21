class ValidationException(Exception):
    """Validation Exception class"""


class ExecuteException(Exception):
    """Raised when commend execution fails"""


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
