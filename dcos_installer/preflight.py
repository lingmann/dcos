import subprocess
import logging as log
import yaml
import os
import datetime


def check(options):
    """
    SSH via SubProcess Calls... 
    """

    ssh_user = open(options.ssh_user_path, 'r').read().lstrip().rstrip()
    hosts_blob = get_inventory(options.hosts_yaml_path)
    preflight_cmd = 'uptime'

    for role, hosts in hosts_blob.items():
        # If our hosts list from yaml has more than 0 hosts in it...
        if len(hosts) > 0:
            log.debug("Rendering inventory %s role with hosts %s", role, hosts)
            host_list = []
            if type(hosts) is str:
                host_list.append(hosts)
            if type(hosts) is list:
                host_list = hosts
    
        
            for host in host_list:
                log.info("Executing preflight on %s role...", host)
                host_stdout = execute_cmd(options.ssh_key_path, ssh_user, host, preflight_cmd)  
                dump_host_results(options, host, host_stdout)
                

        else:
            log.warn("%s is empty, skipping.", role)


def execute_cmd(key_path, user, host, cmd):
    """
    Executes commands on remote machines via SSH protocol.
    """
    execute_cmd = 'ssh -q -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -i {0} {1}@{2} {3}'.format(key_path, user, host, cmd)

    log.debug("Executing %s", execute_cmd)
    process = subprocess.Popen(
        execute_cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT)

    stdout, stderr = process.communicate()
    status = process.poll()
    log.info("%s: %s", host, convert(stdout))

    return convert(stdout)


def convert(input):
    """ 
    Converts the bytes array to utf-8 encoded string.
    """
    return input.decode('utf-8')


def get_inventory(path):
    """
    Returns the inventory in hosts.yaml
    """
    log.debug("Getting host inventory from %s", path)
    hosts = yaml.load(open(path, 'r'))
    return hosts


def dump_host_results(options, host, results):
    timestamp = str(datetime.datetime.now()).split('.')[0]
    current_results = {
        host: {
            timestamp: '{}'.format(results.lstrip().rstrip())
        }
    }
    
    current_file = current_results
    if os.path.exists(options.preflight_results_path): 
        current_file = yaml.load(open(options.preflight_results_path)) 
        current_file[host][timestamp] = results.lstrip().rstrip()

    with open(options.preflight_results_path, 'w') as preflight_file:
        preflight_file.write(yaml.dump(current_results, default_flow_style=False))



