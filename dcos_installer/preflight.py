#import ansible.runner
from ansible.playbook import PlayBook
from ansible import callbacks, utils, runner, inventory

import logging as log
import yaml
import json
from jinja2 import Template
from tempfile import NamedTemporaryFile
import pprint


def check(options):
    """
    A foo def for testing ansible.
    """
    ssh_user = open(options.ssh_user_path, 'r').read()
    hosts_blob = get_inventory(options.hosts_yaml_path)
    for role, hosts in hosts_blob.iteritems():
        # If our hosts list from yaml has more than 0 hosts in it...
        if len(hosts) > 0:
            log.debug("Rendering inventory template for %s role with hosts %s", role, hosts)
            host_list = []
            host_list.append(hosts)
    
            log.info("Executing preflight on %s role...", role)
            # Create an inventory object from the list of hosts in the current role
            inventory_object = inventory.Inventory(host_list)

            # Execute a copy of the dcos_install.sh to the node
            copy_preflight = runner.Runner(
                module_name='copy',
                module_args='src=install_dcos.sh dest=~/install_dcos.sh',
                pattern='all',
                forks=10,
                inventory=inventory_object,
                remote_user=ssh_user,
                private_key_file=options.ssh_key_path,
            )
            
            # Execute the script in --preflight-only mode
            execute_preflight = runner.Runner(
                module_name='command',
                module_args='sudo /bin/bash ~/install_dcos.sh --preflight-only',
                pattern='all',
                forks=10,
                inventory=inventory_object,
                remote_user=ssh_user,
                private_key_file=options.ssh_key_path,
            )

            # Execute a copy then preflight script
            copy_results = copy_preflight.run()
            execute_results = execute_preflight.run()
            
            # Remove unicode text
            copy_results = convert(copy_results)
            dump_host_results(options, copy_results)
            execute_results = convert(execute_results)
            dump_host_results(options, execute_results)
            

        else:
            log.warn("%s is empty, skipping.", role)

def convert(input):
    """ 
    Converts a unicode dict to ascii for yaml dump
    """
    if isinstance(input, dict):
        return {convert(key): convert(value) for key, value in input.iteritems()}
    elif isinstance(input, list):
        return [convert(element) for element in input]
    elif isinstance(input, unicode):
        return input.encode('utf-8')
    else:
        return input

def get_inventory(path):
    log.debug("Getting host inventory from %s", path)
    hosts = yaml.load(open(path, 'r'))
    #inventory = ansible.inventory.Inventory(hosts)
    return hosts

def dump_host_results(options, results):
    with open(options.preflight_results_path, 'a') as preflight_file:
        preflight_file.write(yaml.dump(results, default_flow_style=False))
