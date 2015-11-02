from jinja2 import Template


def setup(options):
    """
    Sets up the ansible configuration file and other basic things.
    """
    ssh_user = open('{}/ssh_user'.format(options.install_directory), 'r').read()
    ansible_cfg_path = '{}/ansible.cfg'.format(options.install_directory)
    ansible_cfg = Template("""
[defaults]
host_key_checking = False
remote_user = {{ ssh_user }}
private_key_file= {{if ssh_key_path:}}{{ssh_key_path}}{{else:}}$HOME/dcos-installer/ssh_key{{endif}}
log_path = DCOS-ssh.log
""")
    with open(ansible_cfg_path, 'w') as f:
        f.write(ansible_cfg.render(
            ssh_user=ssh_user,
            ssh_key_path='{}/ssh_key'.format(options.install_directory)
        ))
    
