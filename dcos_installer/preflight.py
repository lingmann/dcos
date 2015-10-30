import logging as log

import paramiko

import yaml

def check(options, hosts_path):
    """
    Open the hosts file and execute the preflight checks
    per role.
    """
    preflight_output_path = '{}/preflight_check.output'.format(options.install_directory)
    ssh_key_path = '{}/ssh_key'.format(options.install_directory)
    hosts = yaml.load(open(hosts_path, 'r'))
    ssh_user = open('{}/ssh_user'.format(options.install_directory))
    execute_check(preflight_output_path, ssh_key_path, hosts, ssh_user)

def execute_check(output_path, key_path, hosts, username):
    """
    Execute the SSH script to install DCOS over SSH via the Paramiko 
    library.
    """
    ssh = paramiko.SSHClient()
    key = paramiko.RSAKey.from_private_key_file(key_path)
    ssh.set_missing_host_key_policy(
        paramiko.AutoAddPolicy())

    for role in hosts.iteritems():
        log.info("Installing DCOS on %s role hosts.", role)
        install_cmd = '/home/%s/install_dcos.sh %s'.format(username, role)

        for host in role.iteritems():
            log.info("Connecting to %s", host)
            ssh.connect( 
                hostname=host,
                username=username,
                pkey=key)

            log.info('Executing {}'.format(install_cmd))
            stdin , stdout, stderr = ssh.exec_command(install_cmd)
            
            response = {
                "host": {
                    "stdin": stdin,
                    "stdout": stdout,
                    "stderr": stderr
                }
            }
            dump_response(output_path, response)


def dump_response(path, response):
    log.debug("Dumping response to %s", path)
    with open(path, 'w') as f:
        f.write(yaml.dump(response, default_flow_style=False, explicit_start=True))
