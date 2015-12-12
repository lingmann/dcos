import logging
import re

from termcolor import colored

log = logging.getLogger(__name__)


def find_data(data_in):
    failed_data = {}
    success_data = {}
    for data in data_in:
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


class DeployPrettyPrint():
    def __init__(self):
        self.ssh_out = {}

    def beautify(self):
        self.failed_data, self.success_data = find_data(self.ssh_out)
        self.print_data()

    def print_data(self):
        if len(self.failed_data) > 0:
            print(colored('FAILED', 'red'))
            print('')
            for host, data in self.failed_data.items():
                print(colored('     HOST: ', 'yellow'), colored(host, 'red'))
                print(colored('     CODE: ', 'yellow'), colored(data['returncode'], 'red'))
                print(colored('     TASK: ', 'yellow'), colored(' '.join(data['cmd']), 'red'))
                print(colored('     STDERR: ', 'yellow'), colored('\n'.join(data['stderr']), 'red'))
                print(colored('     STDOUT: ', 'yellow'), colored('\n'.join(data['stdout'])))
                print(' ')
        if len(self.success_data) > 0:
            print(colored('SUCCESS', 'green', attrs=['underline']))
            print('')
            for host, data in self.success_data.items():
                print(colored('     HOST: ', 'blue'), colored(host, 'green'))
                print(colored('     CODE: ', 'blue'), colored(data['returncode'], 'green'))
                print(colored('     TASK: ', 'blue'), colored(' '.join(data['cmd']), 'green'))
                print(colored('     STDERR: ', 'blue'), colored(''.join(data['stderr']), 'green'))
                print(colored('     STDOUT: ', 'blue'), colored('\n'.join(data['stdout']), 'green'))
                print(' ')


class PreflightPrettyPrint():
    def __init__(self):
        self.ssh_out = {}

    def beautify(self):
        self.failed_data, self.success_data = find_data(self.ssh_out)
        self.print_data()

    def print_data(self):
        if len(self.failed_data) > 0:
            print(colored('FAILED', 'red', attrs=['underline']))
            print('')
            for host, data in self.failed_data.items():
                print(colored('     HOST: ', 'yellow'), colored(host, 'red'))
                print(colored('     CODE: ', 'yellow'), colored(data['returncode'], 'red'))
                print(colored('     TASK: ', 'yellow'), colored(' '.join(data['cmd']), 'red'))
                print(colored('     STDERR: ', 'yellow'), colored(''.join(data['stderr']), 'red'))
                print(colored('     STDOUT: ', 'yellow'), self.color_preflight(data['stdout']))
                print(' ')

        if len(self.success_data) > 0:
            print(colored('SUCCESS', 'green', attrs=['underline']))
            print('')
            for host, data in self.success_data.items():
                print(colored('     HOST: ', 'blue'), colored(host, 'green'))
                print(colored('     CODE: ', 'blue'), colored(data['returncode'], 'green'))
                print(colored('     TASK: ', 'blue'), colored(' '.join(data['cmd']), 'green'))
                print(colored('     STDERR: ', 'blue'), colored(''.join(data['stderr']), 'green'))
                print(colored('     STDOUT: ', 'blue'), colored('\n'.join(data['stdout']), 'green'))
                print(' ')

    def color_preflight(self, data_array):
        does_pass = re.compile('PASS')
        does_fail = re.compile('FAIL')

        for line in data_array:
            if does_pass.match(line.split('::')[0]):
                print(colored('          {}'.format(line), 'green'))

            if does_fail.match(line):
                print(colored('          {}'.format(line), 'red'))
