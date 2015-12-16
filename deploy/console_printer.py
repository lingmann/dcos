import glob
import logging
import os

import yaml

log = logging.getLogger(__name__)


def print_host_failures(f):
    return_code = False
    for host, data in f.items():
        for timestamp, values in data.items():
            if values['returncode'] is not 0:
                return_code = True

    return return_code, host


def print_header(string):
    delimiter = '====>'
    log.warning('{:5s} {:6s}'.format(delimiter, string))


def print_failures(log_type, directory):
    """
    Glob on the log log_type for log files in log_directory and
    print all hosts with non-zero exit codes.
    """
    check_logs = []
    failed_hosts = 0
    total_hosts = len(glob.glob('{}/*_{}.log'.format(directory, log_type)))

    for yml in glob.glob('{}/*_{}.log'.format(directory, log_type)):
        with open(yml, 'r') as yaml_file:
            f = yaml.load(yaml_file)
            if len(f) > 0:
                failures, host = print_host_failures(f)
                if failures:
                    failed_hosts += 1
                    check_logs.append(yaml_file.name)

    log.info('')
    log.info('')
    print_header('SUMMARY')
    if len(check_logs) > 0:
        log.error('{} out of {} hosts failed {} stage:'.format(failed_hosts, total_hosts, log_type))
        log.error('Errors encountered, please scroll up or run with "--log-level debug" for more details')
        log.warning('Errors detected during {} stage, please check the following logs for details:'.format(log_type))
        for file_path in check_logs:
            log.warning(file_path)
    else:
        log.info('{} out of {} hosts successfully completed {} stage:'.format(total_hosts, total_hosts, log_type))
        log.info('Success, no errors found during {}'.format(log_type))


def clean_logs(log_type, directory):
    for yml in glob.glob('{}/*_{}.log'.format(directory, log_type)):
        log.debug('Cleaning old {} file: {}'.format(log_type, yml))
        os.remove(yml)
