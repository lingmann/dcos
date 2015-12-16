import json
import logging
import pprint
import re

log = logging.getLogger(__name__)


def find_data(data):
    failed_data = {}
    success_data = {}
    for key, value in data.items():
        if key == 'returncode':
            if value != 0:
                failed_data[data['host']['ip']] = {
                    'cmd': data['cmd'],
                    'returncode': data['returncode'],
                    'stdout': data['stdout'],
                    'stderr': data['stderr']
                }

            else:
                success_data[data['host']['ip']] = {
                    'cmd': data['cmd'],
                    'returncode': data['returncode'],
                    'stdout': data['stdout'],
                    'stderr': data['stderr']
                }

    return failed_data, success_data


class PrettyPrint():
    """
    Pretty prints the output from the deployment process.

    """
    def __init__(self, output):
        self.ssh_out = output

    def beautify(self, mode='print_data_basic'):
        self.failed_data, self.success_data = find_data(self.ssh_out)
        getattr(self, mode)()
        return self.failed_data, self.success_data

    def print_data_basic(self):
        if len(self.failed_data) > 0:
            for host, data in self.failed_data.items():
                log = logging.getLogger(host)
                log.error('{} FAILED'.format(host))
                log.debug('     CODE {}'.format(data['returncode']))
                log.error('     TASK {}'.format(' '.join(data['cmd'])))
                log.error('     STDERR {}'.format('\n'.join(data['stderr'])))
                log.error('     STDOUT {}'.format('\n'.join(data['stdout'])))
        if len(self.success_data) > 0:
            for host, data in self.success_data.items():
                log = logging.getLogger(host)
                log.debug('{} SUCCESS'.format(host))
                log.debug('     CODE {}'.format(data['returncode']))
                log.debug('     TASK {}'.format(' '.join(data['cmd'])))
                log.debug('     STDERR {}'.format(''.join(data['stderr'])))
                log.debug('     STDOUT {}'.format('\n'.join(data['stdout'])))

    def print_data_preflight(self):
        if len(self.failed_data) > 0:
            for host, data in self.failed_data.items():
                log = logging.getLogger(host)
                log.error('{} FAILED'.format(host))
                log.debug('     CODE {}'.format(data['returncode']))
                log.error('     TASK {}'.format(' '.join(data['cmd'])))
                log.error('     STDERR {}'.format(''.join(data['stderr'])))
                log.error('     STDOUT {}'.format(self.color_preflight(data['stdout'], host)))

        if len(self.success_data) > 0:
            for host, data in self.success_data.items():
                log = logging.getLogger(host)
                log.debug('{} SUCCESS'.format(host))
                log.debug('     CODE {}'.format(data['returncode']))
                log.debug('     TASK {}'.format(' '.join(data['cmd'])))
                log.debug('     STDERR {}'.format(''.join(data['stderr'])))
                log.debug('     STDOUT {}'.format(self.color_preflight(data['stdout'], host)))

    def print_json(self):
        if len(self.success_data) > 0:
            pprint.pprint(json.dumps(self.success_data))

        if len(self.failed_data) > 0:
            pprint.pprint(json.dumps(self.failed_data))

    def color_preflight(self, data_array, host):
        """
        A subroutine to parse the output from the dcos_install.sh script's pass or fail
        output.
        """
        log = logging.getLogger(host)
        does_pass = re.compile('PASS')
        does_fail = re.compile('FAIL')
        for line in data_array:
            if does_pass.search(line):
                log.debug('          {}'.format(line))

            elif does_fail.search(line):
                log.error('          {}'.format(line))

            else:
                log.debug('          {}'.format(line))
