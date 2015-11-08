import asyncio
import paramiko
import subprocess
import sys
import logging as log
import yaml
import os
import datetime


def check(options):
    """
    SSH via SubProcess Calls... 
    """
    ssh_user = open(options.ssh_user_path, 'r').read().lstrip().rstrip()
    hosts_blob = get_inventory(options.hosts_yaml_path)
    preflight_cmd = 'sudo bash /home/{}/install_dcos.sh --preflight-only'.format(ssh_user)

    for role, hosts in hosts_blob.items():
        # If our hosts list from yaml has more than 0 hosts in it...
        if len(hosts) > 0:
            log.debug("Rendering inventory %s role with hosts %s", role, hosts)
            host_list = []
            if type(hosts) is str:
                host_list.append(hosts)
            if type(hosts) is list:
                host_list = hosts
    
        
            for host in host_list:
                log.info("Copying %s to %s...",options.dcos_install_script_path, host)
                
                # Copy install_dcos.sh
                # Assumes the user given has a home directory
                copy_data = copy_cmd(
                    options.ssh_key_path, 
                    ssh_user, 
                    host, 
                    options.dcos_install_script_path, 
                    '~/install_dcos.sh')

                dump_host_results(options, host, copy_data)
                log.info("Executing preflight on %s role...", host)
                
                # Execute the preflight command
                host_data = execute_cmd(
                    options.ssh_key_path, 
                    ssh_user, 
                    host, 
                    preflight_cmd)  
                
                # Dump to structured data
                dump_host_results(options, host, host_data)

        else:
            log.warn("%s is empty, skipping.", role)

def get_structured_results(host, cmd, retcode, stdout, stderr):
    """
    Takes the output from a SSH run and returns structured output for the 
    log file.
    """
    timestamp = str(datetime.datetime.now()).split('.')[0]
    if type(stdout) is not str:
        stdout = convert(stdout.read())
    
    if type(stderr) is not str:
        stderr = convert(stderr.read())

    struct_data = {
        host: {
            timestamp: {
                'cmd': cmd,
                'retcode': retcode,
                'stdout': stdout,
                'stderr': stderr 
            }
        }
    }
    log.debug("Structured data:")
    print(struct_data)
    return struct_data


def execute_cmd(key_path, user, host, cmd):
    """
    Executes commands on remote machines via SSH protocol.
    """
    try:
        key = paramiko.RSAKey.from_private_key_file(key_path)
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        log.debug("Connecting to %s", host)
        client.connect(
            hostname=host,
            username=user,
            timeout=3,
            pkey=key)
            
        log.debug("Executing %s", execute_cmd)
        stdin, stdout, stderr = client.exec_command(cmd)
        retcode = stdout.channel.recv_exit_status()
        return get_structured_results(host, cmd, retcode, stdout, stderr)

    except: 
        e = sys.exc_info()[0]
        log.error(e)
        retcode = 1
        stdout = ''
        stderr = str(e)
        return get_structured_results(host, cmd, retcode, stdout, stderr)



def copy_cmd(key_path, user, host, local_path, remote_path):
    """
    Copies arbitrary things to arbitrary places.
    """
    copy_cmd = 'scp -q -o ConnectTimeout=3 -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -i {0} {1} {2}@{3}:{4}'.format(
        key_path, 
        local_path, 
        user, 
        host, 
        remote_path)
    
    try:
        log.info("Executing %s...", copy_cmd)
        process = subprocess.Popen(
            copy_cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT)

        stdout, stderr = process.communicate()
        process.poll()
        retcode = process.returncode
        log.warn(retcode)
        log.info("%s: %s", host, convert(stdout))
        return get_structured_results(host, copy_cmd, retcode, stdout, stderr)

    except:
        e = sys.exc_info()[0]
        log.error(e)
        retcode = 1
        stdout = '' 
        stderr = str(stdout)
        return get_structured_results(host, copy_cmd, retcode, stdout, stderr)


    return convert(stdout)


def convert(input):
    """ 
    Converts the bytes array to utf-8 encoded string.
    """
    return input.decode('utf-8')


def get_inventory(path):
    """
    Returns the inventory in hosts.yaml
    """
    log.debug("Getting host inventory from %s", path)
    hosts = yaml.load(open(path, 'r'))
    return hosts


def dump_host_results(options, host, results):
    """
    Dumps the results to our preflight log file. Assumes incoming results are already
    pre-structured. 
    """
    if os.path.exists(options.preflight_results_path): 
        current_file = yaml.load(open(options.preflight_results_path)) 
        for fhost, data in current_file.items():
            if host == fhost:
                for timestamp, values in data.items():
                    results[fhost][timestamp] = values

            else:
                results[fhost] = data
        

    with open(options.preflight_results_path, 'w') as preflight_file:
        preflight_file.write(yaml.dump(results, default_flow_style=False))
