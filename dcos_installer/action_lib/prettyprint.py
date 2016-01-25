import json
import logging
import pprint
import re

log = logging.getLogger(__name__)



def print_header(string):
    delimiter = '====>'
    log.warning('{:5s} {:6s}'.format(delimiter, string))


class PrettyPrint():
    """
    Pretty prints the output from the deployment process.

    """
    def __init__(self, output):
        self.ssh_out = output
        self.fail_hosts = {}
        self.success_hosts = {}
        self.stage_name = 'NULL'

    def beautify(self, mode='print_data_basic'):
        self.failed_data, self.success_data = self.find_data(self.ssh_out)
        getattr(self, mode)()
        return self.failed_data, self.success_data

    def find_data(self, data):
        failed_data = []
        success_data = []
        for hosts in data:
            for host in hosts:
                for ip, results in host.items():
                    if results['returncode'] == 0:
                        self.fail_hosts[ip] = 1
                        success_data.append(host)
                    else:
                        self.success_hosts[ip] = 1
                        failed_data.append(host)

        return failed_data, success_data


    def print_data(self):
        if len(self.failed_data) > 0:
            for host in self.failed_data:
                for ip, data in host.items():
                    log = logging.getLogger(str(ip))
                    log.error('{} FAILED'.format(ip))
                    log.debug('     CODE:\n{}'.format(data['returncode']))
                    log.error('     TASK:\n{}'.format(' '.join(data['cmd'])))
                    log.error('     STDERR:\n{}'.format(''.join(data['stderr'])))
                    if len(data['stdout']) > 0:
                        log.error('     STDOUT:\n{}'.format('\n'.join(data['stdout'])))

        if len(self.success_data) > 0:
            for host in self.success_data:
                for ip, data in host.items():
                    log = logging.getLogger(str(ip))
                    log.debug('{} SUCCESS'.format(ip))
                    log.debug('     CODE\n{}'.format(data['returncode']))
                    log.debug('     TASK\n{}'.format(' '.join(data['cmd'])))
                    log.debug('     STDERR\n{}'.format('\n'.join(data['stderr'])))
                    if len(data['stdout']) > 0 and data['stdout'] != ['']:
                        log.info('      STDOUT\n{}'.format('\n'.join(data['stdout'])))

    def print_summary(self):
        print_header('SUMMARY')
        log.warning('{} hosts failed {} stage.'.format(len(self.fail_hosts), self.stage_name))
        for host, index in self.failed_hosts.items():
            log.error('     {} failures detected.'.format(host))


    def print_json(self):
        pprint.pprint(json.dumps(self.ssh_out))
#        if len(self.success_data) > 0:
#            pprint.pprint(json.dumps(self.success_data))
#
#        if len(self.failed_data) > 0:
#            pprint.pprint(json.dumps(self.failed_data))
