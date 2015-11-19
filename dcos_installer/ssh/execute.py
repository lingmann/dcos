import subprocess
import threading
import time
import os
import Queue
import yaml

from dcos_installer.log import DCOSLog
log = DCOSLog(__name__).log


class DCOSRemoteCmd(object):
    """
    Executes commands on machines remotely by shelling out 
    to SSH and leveraging threading for concurrent sessions. 
    """
    def __init__(self, options):
        """
        Setup the remote command class.
        """
        # Defaults from CLI
        self.log_directory = options.log_directory
        self.concurrent_sessions = options.concurrent_sessions
        self.inventory_path = options.host_yaml_path
        self.ssh_user = None
        self.ssh_user_path = options.ssh_user_path
        self.ssh_key_path = None         

        # Class defaults
        self.response_queue = Queue.Queue()
        self.command = ''
        

    def execute(self):
        """
        Executes arbitrary commands asynchronously using multithreads.
        """
        # Get the inventory for the session
        inventory = self.get_inventory() 
        running_threads = []

        # Sanity check the ssh_user and ssh_key_paths and if not set, do the right thing (tm)
        if self.ssh_user == None:
            log.warning("SSH user left unset, attempting to load from default %s", self.ssh_user_path)
            try:
                self.ssh_user = open(self.ssh_user_path, 'r').read().lstrip().rstrip()

            except:
                log.error("Unable to get a valid user for SSH session. DCOSRemoteCmd.ssh_user is unset and %s is not found", self.ssh_user_path)


        elif self.ssh_key_path == None: 
            log.warning("SSH key path left unset, attempting to load from default %s", self.ssh_key_path)
            try:
                os.stat(self.ssh_key_path)

            except:
                log.error("Unable to set a valid SSH key path. DCOSRemoteCmd.ssh_key_path is unset and %s is not found", self.ssh_key_path)
        
        elif self.ssh_key_path != None:
            try:
                os.stat(self.ssh_key_path) 

            except:
                log.error("Unable to stat %s. Please make sure it exists.", self.ssh_key_path)


        else:
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
                            t = threading.Thread(name='{}_execute_cmd'.format(host), target=self.do_thread, args=(options, host,))
                            running_threads.append(p)
                            t.daemon = True
                            p.start()

                    else:
                        for thread in running_threads:
                            if not thread.is_alive():
                                running_threads.remove(thread)


                else:
                    log.warn("%s is empty, skipping.", role)
 

    def do_thread(self, options, host):
        """
        Execute a SSH thread and run a command on an arbitrary host.
        """
        # Define the SSH command to run
        ssh_cmd = 'ssh -q -o ConnectTimeout=3 -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -i {0} {1}@{2} {3}'.format(
            self.ssh_key_path,
            self.ssh_user,
            host,
            self.command)

        try:
            log.info("Executing %s on %s.", self.command, host)
            process = subprocess.Popen(
                ssh_cmd,
                shell=True,
                stdout=subprocess.STDOUT,
                stderr=subprocess.STDERR)

            stdout, stderr = process.communicate
            process.poll()
            retcode = process.returncode
            log.info("%s: %s", host, convert(stdout))
            


    def get_inventory(self):
        """
        Returns the inventory in hosts.yaml
        """
        log.debug("Getting host inventory from %s", self.inventory_path)
        hosts = yaml.load(open(self.inventory_path, 'r'))
        return hosts
