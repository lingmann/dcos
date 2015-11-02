from jinja2 import Template
import logging as log

def setup(options):
    """
    Sets up the ansible configuration file and other basic things.
    """
    ansible_validation, validation_message = validate_ansible_dependencies(options):
    if ansible_validation:
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
    else:
        log.error("Not all ansible dependencies were met: %s", validation_message)
    

def validate_ansible_dependencies(options):
    """
    Validate that the paths to ansible dependencies exist and that they
    contain data.
    """

