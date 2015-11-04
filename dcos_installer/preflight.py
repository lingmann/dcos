from ansible import runner, inventory
import logging as log
import yaml
import os


def check(options):
    """
    Starting over. 
    """

    ssh_user = open(options.ssh_user_path, 'r').read()
    hosts_blob = get_inventory(options.hosts_yaml_path)
    
    for role, hosts in hosts_blob.items():
        # If our hosts list from yaml has more than 0 hosts in it...
        if len(hosts) > 0:
            log.debug("Rendering inventory %s role with hosts %s", role, hosts)
            host_list = []
            if type(hosts) is str:
                host_list.append(hosts)
            if type(hosts) is list:
                host_list = hosts
    
            log.info("Executing preflight on %s role...", role)
#            execute_results = convert(execute_results)
#            dump_host_results(options, execute_results)
            

        else:
            log.warn("%s is empty, skipping.", role)

def convert(input):
    """ 
    Converts a unicode dict to ascii for yaml dump
    """
    if isinstance(input, dict):
        return {convert(key): convert(value) for key, value in input.items()}
    elif isinstance(input, list):
        return [convert(element) for element in input]
    elif isinstance(input, str):
        return input.encode('utf-8')
    else:
        return input

def get_inventory(path):
    log.debug("Getting host inventory from %s", path)
    hosts = yaml.load(open(path, 'r'))
    #inventory = ansible.inventory.Inventory(hosts)
    return hosts

def dump_host_results(options, results):
    if os.path.exists(options.preflight_results_path): 
        current_data = yaml.load(open(options.preflight_results_path)) 
            
        for status, data in current_data.items():
            for key, values in data.items():
                results[status][key] = values

    with open(options.preflight_results_path, 'w') as preflight_file:
        preflight_file.write(yaml.dump(results, default_flow_style=False))



