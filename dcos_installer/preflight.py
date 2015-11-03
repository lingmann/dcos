import ansible.runner
from ansible.playbook import PlayBook
import ansible.inventory 
from ansible import callbacks
from ansible import utils

import logging as log
import sys
import yaml
from jinja2 import Template
from tempfile import NamedTemporaryFile


def create_playbook(options):
    """
    Dynamically generate the ansible playbook for our roles.
    """
    ansible_playbook = """
- hosts:
    - master
    - slave_public
    - slave_private
  tasks:
    - name: preflight
      command: uptime
"""
    log.debug("Generating playbook...")
    print(ansible_playbook)
    with open(options.playbook_path, 'w') as f:
          f.write(ansible_playbook)


def uptime(options):
    """
    A foo def for testing ansible.
    """
    create_playbook(options)
    utils.VERBOSITY = 4 
    playbook_cb = callbacks.PlaybookCallbacks(verbose=utils.VERBOSITY)
    stats = callbacks.AggregateStats()
    runner_cb = callbacks.PlaybookRunnerCallbacks(stats, verbose=utils.VERBOSITY)

    ssh_user = open(options.ssh_user_path, 'r').read()
    inventory = get_inventory(options.hosts_yaml_path)
    for role, hosts in inventory.iteritems():
        # If our hosts list from yaml has more than 0 hosts in it...
        if len(hosts) > 0:
            log.debug("Rendering inventory template for %s role with hosts %s", role, hosts)
            # HACK ATTACK: inventory file must be present even if I pass a list of hosts, so....
            inventory = """
            [{{ role }}]
            {{hosts}}
            """
            inventory_template = Template(inventory)
            rendered_inventory = inventory_template.render(
                role=role,
                hosts=hosts)
    
            print(rendered_inventory)
            hosts = NamedTemporaryFile(delete=False)
            hosts.write(rendered_inventory)
            hosts.close()

            log.info("Executing preflight on %s role...", role)
            pb = PlayBook(
                playbook=options.playbook_path,
                host_list=hosts.name,     
                remote_user=ssh_user,
                callbacks=playbook_cb,
                runner_callbacks=runner_cb,
                stats=stats,
                private_key_file=options.ssh_key_path
            )
            results = pb.run()
            playbook_cb.on_stats(pb.stats)

            log.info("RESULTS #####")
            print results
        else:
            log.warn("%s is empty, skipping.", role)

    

def get_inventory(path):
    log.debug("Getting host inventory from %s", path)
    hosts = yaml.load(open(path, 'r'))
    #inventory = ansible.inventory.Inventory(hosts)
    return hosts
