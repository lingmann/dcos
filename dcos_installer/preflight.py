import logging as log
import paramiko
import sys
import yaml


def check(options, hosts_path):
    """
    Open the hosts file and execute the preflight checks
    per role.
    """
    preflight_output_path = '{}/preflight_check.output'.format(options.install_directory)
    ssh_key_path = '{}/ssh_key'.format(options.install_directory)
    hosts = yaml.load(open(hosts_path, 'r'))
    ssh_user = open('{}/ssh_user'.format(options.install_directory)).read()
    
    for role, host_list in hosts.iteritems():
        log.debug("Host list: %s, Role: %s", host_list, role)
        for host in host_list.split(','):
            # Upload the preflight script
            upload(preflight_output_path, ssh_key_path, host, ssh_user)

            # Execute installation
            return execute_check(preflight_output_path, ssh_key_path, host, ssh_user)


def upload(output_path, key_path, host, username):
    """
    Upload the preflight script to the host via paramiko SSH API.
    """
    import logging as log
    log.basicConfig(filename='preflight.log', filemode='w', level=log.DEBUG)

    log.info("Attempting to transfer preflight.sh...")
    log.info("Key path %s", key_path)
    log.info("Hostname: %s", host)
    log.info("Username: %s", username)
    # Create a new SFTP object
    # Get the key 
    key = paramiko.RSAKey.from_private_key_file(key_path)
    # Set the hostname missing policy so we don't need it in authorized_hosts

    try:
        transport = paramiko.Transport(host, 22)
        transport.connect(username = username, pkey = key)
        sftp = paramiko.SFTPClient.from_transport(transport)
        sftp.put('preflight.sh', '/home/vagrant/preflight.sh')
        sftp.close()
        transport.close()
        return

    except:
        log.error("Problem uploading preflight script.")
        log.error(sys.exc_info()[0])
        pass


def execute_check(output_path, key_path, host, username):
    """
    Execute the SSH script to install DCOS over SSH via the Paramiko 
    library.
    """
    preflight_cmd = '/bin/bash $HOME/preflight.sh'.format(username)
    ssh = paramiko.SSHClient()
    key = paramiko.RSAKey.from_private_key_file(key_path)
    paramiko.util.log_to_file('test.log')
    ssh.set_missing_host_key_policy(
        paramiko.AutoAddPolicy())
    # Execute command via SSH
    try:
        log.info("Connecting to %s@%s", username, host)
        ssh.connect( 
            hostname=host,
            username=username,
            pkey=key)

        log.info('Executing {}'.format(preflight_cmd))
        stdin, stdout, stderr = ssh.exec_command(preflight_cmd)
        
        yield stdout, stderr
#        response = {
#            "host": {
#                "stdin": stdin,
#                "stdout": stdout,
#                "stderr": stderr
#            }
#        }
#        dump_response(output_path, response)
    except:
        log.error("Connection issue with %s", host)
        yield "An error occured", log.error(sys.exc_info()[0])


def dump_response(path, response):
    log.debug("Dumping response to %s", path)
    with open(path, 'w') as f:
        f.write(yaml.dump(response, default_flow_style=False, explicit_start=True))
