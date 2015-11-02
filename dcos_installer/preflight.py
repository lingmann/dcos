import ansible.runner
import ansible.inventory 
import logging as log
import sys
import yaml

def uptime(options):
    """
    A foo def for testing ansible.
    """
    # Our hosts.yaml path 
    inventory_path = '{}/hosts.yaml'.format(options.install_directory)
    # construct the ansible runner and execute on all hosts
    results = ansible.runner.Runner(
        pattern='*',
        forks=10,
        module_name='command',
        module_args='/usr/bin/uptime',
        inventory=get_inventory(inventory_path)
    ).run()

    if results is None:
       print "No hosts found"
       sys.exit(1)

    print "UP ***********"
    for (hostname, result) in results['contacted'].items():
        if not 'failed' in result:
            print "%s >>> %s" % (hostname, result['stdout'])

    print "FAILED *******"
    for (hostname, result) in results['contacted'].items():
        if 'failed' in result:
            print "%s >>> %s" % (hostname, result['msg'])

    print "DOWN *********"
    for (hostname, result) in results['dark'].items():
        print "%s >>> %s" % (hostname, result)


def get_inventory(path):
    log.debug("Getting host inventory from %", path)
    hosts = yaml.load(open(path, 'r'))
    log.debug("Hosts: %s", hosts)
    inventory = ansible.inventory.Inventory(hosts)
    return inventory
