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


def setup(options):
  """
  Sets up the ansible configuration file and other basic things.
  """
  ssh_user = open(options.ssh_user_path, 'r').read()
  ansible_cfg = Template("""
[defaults]
host_key_checking = False
remote_user = {{ ssh_user }}
private_key_file= {{ssh_key_path}}
log_path = DCOS-ssh.log
""")

  with open(options.ansible_cfg_path, 'w') as f:
      f.write(ansible_cfg.render(
          ssh_user=ssh_user,
          ssh_key_path=options.ssh_key_path
      ))

  log.info("Ansible configration at %s", options.ansible_cfg_path)
  print(ansible_cfg.render(
      ssh_user=ssh_user,
      ssh_key_path=options.ssh_key_path
  ))


def create_playbook(options):
    """
    Creates the ansible playbook for our roles.
    """
    ansible_playbook = """
- hosts: master 
  tasks:
    - name: preflight
      command: uptime
"""
    with open(options.playbook_path, 'w') as f:
          f.write(ansible_playbook)


def uptime(options):
    """
    A foo def for testing ansible.
    """
    create_playbook(options)
    utils.VERBOSITY = 0
    playbook_cb = callbacks.PlaybookCallbacks(verbose=utils.VERBOSITY)
    stats = callbacks.AggregateStats()
    runner_cb = callbacks.PlaybookRunnerCallbacks(stats, verbose=utils.VERBOSITY)
    ssh_user = open(options.ssh_user_path, 'r').read()
    inventory = get_inventory(options.hosts_yaml_path)
    print(inventory)
    for role, hosts in inventory.iteritems():
        print(type(hosts))
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
        else:
            log.warn("%s is empty, skipping.", role)

    results = pb.run()
    playbook_cb.on_stats(pb.stats)

    print results


def get_inventory(path):
    log.debug("Getting host inventory from %s", path)
    hosts = yaml.load(open(path, 'r'))
    #inventory = ansible.inventory.Inventory(hosts)
    return hosts
