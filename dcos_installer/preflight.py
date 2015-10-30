from fabric import *
from fabric.contrib import confirm
import logging as log


def check(options, hosts_path):
    """
    Open the hosts file and execute the preflight checks
    per role.
    """
    preflight_output_path = '{}/preflight_check.output'.format(options.install_directory)

    hosts = yaml.load(open(hosts_path, 'r'))
    for role in hosts.iteritems():
        dump_response(preflight_output_path, execute_check(role, hosts[role]))   


def execute_check(role, hosts):
    for host in hosts:
        log.info("Executing preflight check on %s", host)
        # returning foo data for now
        return {
            'code': 0,
            'host': host,
            'response': 'success'
        }


def dump_response(path, response):
    log.debug("Dumping response to %s", path)
    with open(path, 'w') as f:
        f.write(yaml.dump(response, default_flow_style=False, explicit_start=True))
