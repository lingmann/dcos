import ansible.runner
import ansible.inventory 
import logging as log
import sys
import yaml
from jinja2 import Template


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
- hosts: *
  tasks:
    - name: preflight
      command: uptime
"""
    with open(options.ansible_playbook_path, 'w') as f:
          f.write(ansible_playbook)


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
    inventory = ansible.inventory.Inventory(hosts)
    return inventory
