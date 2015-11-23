# Example Usage:
# ssh_user = 'vagrant' 
#
# preflight = DCOSRemoteCmd()
# preflight.ssh_user = ssh_user
# preflight.ssh_key_path = options.ssh_key_path
# preflight.inventory_path = options.hosts_yaml_path
# preflight.log_directory = options.log_directory
# preflight.command = 'sudo bash /home/{}/install_dcos.sh --preflight-only'.format(ssh_user)
# err = preflight.validate()
# if err:
#   log.error("Could not execute preflight, errors encountered during validation.")
#   log.error(err)
#
# else:
#   preflight.execute()

import datetime
import os
import subprocess
import sys
import threading
import time

import yaml
from dcos_installer.log import DCOSLog

log = DCOSLog(__name__).log


class DCOSRemoteCmd(object):
    """
    Executes commands on machines remotely by shelling out 
    to SSH and leveraging threading for concurrent sessions. 
    """
    def __init__(self):
        """
        Setup the remote command class.
        """
        # Defaults from CLI
        self.log_directory = None
        self.concurrent_sessions = 10 
        self.inventory_path = None 
        self.ssh_user = None
        self.ssh_key_path = None         

        # Class defaults
        self.command = None 
        
    def validate(self):
        """
        Sanity check the ssh_user and ssh_key_paths and if not set, do the right thing (tm)
        """
        errors = {} 
        
        def is_not_none(keys):
            for key, value in keys.items():
                if value == None:
                    errors[key] = 'Is set to {}, please set it before continuing'.format(value)

        def is_string(keys):
            for key, value in keys.items():
                if type(value) != str:
                    errors[key] = '{} must be a string.'.format(key)

        def is_int(keys):
            for key, value in keys.items():
                if type(value) != int:
                    errors[key] = '{} must be an integer.'.format(key)

        def file_does_exist(keys):
            for key, value in keys.items():
                if value is not None:
                    if not os.stat(value):
                        errors[key] = '{} is not present on the filesystem.'.format(value)
                
                else:
                    errors[key] = '{} is set to None, please set it to an actual path.'.format(key)


        is_not_none({
            'DCOSRemoteCmd.log_directory': self.log_directory, 
            'DCOSRemoteCmd.concurrent_sessions': self.concurrent_sessions, 
            'DCOSRemoteCmd.inventory_path': self.inventory_path, 
            'DCOSRemoteCmd.ssh_user': self.ssh_user, 
            'DCOSRemoteCmd.ssh_key_path': self.ssh_key_path, 
            'DCOSRemoteCmd.command': self.command})
        
        is_string({
            'DCOSRemoteCmd.log_directory': self.log_directory, 
            'DCOSRemoteCmd.inventory_path': self.inventory_path, 
            'DCOSRemoteCmd.ssh_user': self.ssh_user, 
            'DCOSRemoteCmd.ssh_key_path': self.ssh_key_path, 
            'DCOSRemoteCmd.command': self.command})


        is_int({
            'DCOSRemoteCmd.concurrent_sessions': self.concurrent_sessions})

        file_does_exist({
            'DCOSRemoteCmd.log_directory': self.log_directory, 
            'DCOSRemoteCmd.inventory_path': self.inventory_path, 
            'DCOSRemoteCmd.ssh_key_path': self.ssh_key_path})

        if len(errors) > 0:
            return errors
        
        else:
            return True


    def execute(self):
        """
        Executes arbitrary commands asynchronously using multithreads.
        """
        # Get the inventory for the session
        inventory = self.get_inventory() 
        running_threads = []

        # If the user path isn't none, we can continue
        for role, hosts in inventory.items():
            # If our hosts list from yaml has more than 0 hosts in it...
            if len(hosts) > 0:
                if len(running_threads) <= self.concurrent_sessions:

                    log.debug("Rendering inventory %s role with hosts %s", role, hosts)

                    if type(hosts) is str:
                        host_list = [hosts]
                    if type(hosts) is list:
                        host_list = hosts

                    for host in host_list:
                        # Spawn a subprocess for preflight
                        t = threading.Thread(name='{}_execute_cmd'.format(host), target=self.do_thread, args=(host,))
                        running_threads.append(t)
                        t.daemon = True
                        t.start()

                else:
                    for thread in running_threads:
                        if not thread.is_alive():
                            running_threads.remove(thread)


            else:
                log.warn("%s is empty, skipping.", role)
 

    def do_thread(self, host):
        """
        Execute a SSH thread and run a command on an arbitrary host.
        """
        # Define the SSH command to run
        ssh_cmd = 'ssh -o ConnectTimeout=3 -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -i {0} {1}@{2} \'{3}\''.format(
            self.ssh_key_path,
            self.ssh_user,
            host,
            self.command)

        log.info("Executing %s on %s.", self.command, host)
        process = subprocess.Popen(
            ssh_cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)

        try:
            stdout, stderr = process.communicate(timeout=15)
            process.poll()
            retcode = process.returncode
            self.dump_host_results(host, self.get_structured_results(
                host, 
                retcode, 
                self.convert(stdout), 
                self.convert(stderr)))

            log.info("%s STDOUT: %s", host, self.convert(stdout))
            log.info("%s STDERR: %s", host, self.convert(stderr))
            
        except:
            process.kill()
            stdout, stderr = process.communicate()
            retcode = process.returncode
            self.dump_host_results(host, self.get_structured_results(host, retcode, stdout, stderr))
            log.info("%s STDOUT: %s", host, self.convert(stdout))
            log.info("%s STDERR: %s", host, self.convert(stderr))

            
    def get_structured_results(self, host, retcode, stdout, stderr):
        """
        Takes the output from a SSH run and returns structured output for the
        log file.
        """
        cmd = self.command
        timestamp = str(datetime.datetime.now()).split('.')[0]
        if type(stdout) is not str:
            try:
                stdout = self.convert(stdout.read())

            except: 
                stdout = str(stdout)

        if type(stderr) is not str:
            try:
                stderr = self.convert(stderr.read())

            except:
                stderr = str(stderr)

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
        return struct_data


    def get_inventory(self):
        """
        Returns the inventory in hosts.yaml
        """
        log.debug("Getting host inventory from %s", self.inventory_path)
        hosts = yaml.load(open(self.inventory_path, 'r'))
        return hosts


    def convert(self, input):
        """
        Converts the bytes array to utf-8 encoded string.
        """
        return input.decode('utf-8') 


    def dump_host_results(self, host, results):
        """
        Dumps the results to our preflight log file. Assumes incoming results are already
        pre-structured.
        """
        log_file = '{}/{}_preflight.log'.format(self.log_directory, host)
        if os.path.exists(log_file):
            current_file = yaml.load(open(log_file))
            for fhost, data in current_file.items():
                if host == fhost:
                    for timestamp, values in data.items():
                        results[fhost][timestamp] = values

                else:
                    results[fhost] = data

        with open(log_file, 'w') as preflight_file:
            preflight_file.write(yaml.dump(results, default_flow_style=False))
