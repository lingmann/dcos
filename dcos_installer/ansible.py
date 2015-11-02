from jinja2 import Template
import logging as log
from . import server

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


    
