import paramiko
import multiprocessing as mp
from multiprocessing import Process
import sys
import subprocess
import time
#import logging
import yaml
import os
import datetime

# Setup logging for multiprocess
from dcos_installer.log import DCOSLog
log = DCOSLog(__name__).log
mp.log_to_stderr()

# Import our ssh submodule
from dcos_installer.ssh.execute import DCOSRemoteCmd


def check(options):
    """
    SSH via SubProcess Calls... 
    """
    ssh_user = open(options.ssh_user_path, 'r').read().lstrip().rstrip()

    preflight = DCOSRemoteCmd()
    preflight.ssh_user = ssh_user 
    preflight.ssh_key_path = options.ssh_key_path
    preflight.inventory_path = options.hosts_yaml_path
    preflight.log_directory = options.log_directory
    preflight.command = 'sudo bash /home/{}/install_dcos.sh --preflight-only'.format(ssh_user)
    err = preflight.validate()
    if err:
        log.error("Could not execute preflight, errors encountered during validation.")
        log.error(err)

    else:
        preflight.execute()
      

#    hosts_blob = get_inventory(options.hosts_yaml_path)
#    
#    # Multiprocessing 
#    concurrent_procs = 10
#    running_procs = [] 
#    for role, hosts in hosts_blob.items():
#
#        # If our hosts list from yaml has more than 0 hosts in it...
#        if len(hosts) > 0:
#            if len(running_procs) <= concurrent_procs:
#                
#                log.debug("Rendering inventory %s role with hosts %s", role, hosts)
#
#
#                if type(hosts) is str:
#                    host_list = [hosts]
#                if type(hosts) is list:
#                    host_list = hosts
#        
#            
#                for host in host_list:
#                    # Spawn a subprocess for preflight
#                    p = Process(name='{}_preflight_worker'.format(host), target=execute_preflight, args=(options, host,))
#                    running_procs.append(p)
#                    #p.daemon = True
#                    p.start()
#            
#            else:
#                for proc in running_procs:
#                    if not proc.is_alive():
#                        running_procs.remove(proc)
#
#
#        else:
#            log.warn("%s is empty, skipping.", role)
#
#
#def execute_preflight(options, host):
#    """
#    Executes SCPing and SSHing to execute preflight on host
#    machines.
#    """
#    ssh_user = open(options.ssh_user_path, 'r').read().lstrip().rstrip()
#    preflight_cmd = 'sudo bash /home/{}/install_dcos.sh --preflight-only'.format(ssh_user)
#    log.info("Copying %s to %s...",options.dcos_install_script_path, host)
#    
#    # Copy install_dcos.sh
#    # Assumes the user given has a home directory
#    copy_data = copy_cmd(
#        options.ssh_key_path, 
#        ssh_user, 
#        host, 
#        options.dcos_install_script_path, 
#        '~/install_dcos.sh')
#
#    dump_host_results(options, host, copy_data)
#    log.info("Executing preflight on %s role...", host)
#    
#    # Execute the preflight command
#    host_data = execute_cmd(
#        options.ssh_key_path, 
#        ssh_user, 
#        host, 
#        preflight_cmd)  
#    
#    # Dump to structured data
#    # Also a child process which retains a lock to ensure we do not 
#    # create a race condition on the log file
#    dump_host_results(options, host, host_data)
#    time.sleep(50)
#
#        
#def get_structured_results(host, cmd, retcode, stdout, stderr):
#    """
#    Takes the output from a SSH run and returns structured output for the 
#    log file.
#    """
#    timestamp = str(datetime.datetime.now()).split('.')[0]
#    if type(stdout) is not str:
#        stdout = convert(stdout.read())
#    
#    if type(stderr) is not str:
#        stderr = convert(stderr.read())
#
#    struct_data = {
#        host: {
#            timestamp: {
#                'cmd': cmd,
#                'retcode': retcode,
#                'stdout': stdout,
#                'stderr': stderr 
#            }
#        }
#    }
#    log.debug("Structured data:")
#    return struct_data
#
#
#def execute_cmd(key_path, user, host, cmd):
#    """
#    Executes commands on remote machines via SSH protocol.
#    """
#    try:
#        key = paramiko.RSAKey.from_private_key_file(key_path)
#        client = paramiko.SSHClient()
#        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
#        log.debug("Connecting to %s", host)
#        client.connect(
#            hostname=host,
#            username=user,
#            timeout=3,
#            pkey=key)
#            
#        log.debug("Executing %s", execute_cmd)
#        stdin, stdout, stderr = client.exec_command(cmd)
#        retcode = stdout.channel.recv_exit_status()
#        return get_structured_results(host, cmd, retcode, stdout, stderr)
#
#    except: 
#        e = sys.exc_info()[0]
#        log.error(e)
#        retcode = 1
#        stdout = ''
#        stderr = str(e)
#        return get_structured_results(host, cmd, retcode, stdout, stderr)
#
#
#
#def copy_cmd(key_path, user, host, local_path, remote_path):
#    """
#    Copies arbitrary things to arbitrary places.
#    """
#    copy_cmd = 'scp -q -o ConnectTimeout=3 -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -i {0} {1} {2}@{3}:{4}'.format(
#        key_path, 
#        local_path, 
#        user, 
#        host, 
#        remote_path)
#    
#    try:
#        log.info("Executing %s...", copy_cmd)
#        process = subprocess.Popen(
#            copy_cmd,
#            shell=True,
#            stdout=subprocess.PIPE,
#            stderr=subprocess.STDOUT)
#
#        stdout, stderr = process.communicate()
#        process.poll()
#        retcode = process.returncode
#        log.warn(retcode)
#        log.info("%s: %s", host, convert(stdout))
#        return get_structured_results(host, copy_cmd, retcode, stdout, stderr)
#
#    except:
#        e = sys.exc_info()[0]
#        log.error(e)
#        retcode = 1
#        stdout = '' 
#        stderr = str(stdout)
#        return get_structured_results(host, copy_cmd, retcode, stdout, stderr)
#
#
#    return convert(stdout)
#
#
#def convert(input):
#    """ 
#    Converts the bytes array to utf-8 encoded string.
#    """
#    return input.decode('utf-8')
#
#
#def get_inventory(path):
#    """
#    Returns the inventory in hosts.yaml
#    """
#    log.debug("Getting host inventory from %s", path)
#    hosts = yaml.load(open(path, 'r'))
#    return hosts
#
#
#def dump_host_results(options, host, results):
#    """
#    Dumps the results to our preflight log file. Assumes incoming results are already
#    pre-structured. 
#    """
#    log_file = '{}/{}_preflight.log'.format(options.log_directory, host)
#    if os.path.exists(log_file): 
#        current_file = yaml.load(open(log_file)) 
#        for fhost, data in current_file.items():
#            if host == fhost:
#                for timestamp, values in data.items():
#                    results[fhost][timestamp] = values
#
#            else:
#                results[fhost] = data
#        
#
#    with open(log_file, 'w') as preflight_file:
#        preflight_file.write(yaml.dump(results, default_flow_style=False))
