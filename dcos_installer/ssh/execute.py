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
                        p = Process(name='{}_preflight_worker'.format(host), target=execute_preflight, args=(options, host  ,))
                        running_procs.append(p)
                       #p.daemon = True
                        p.start()

                else:
                    for thread in running_threads:
                        if not proc.is_alive():
                            running_threads.remove(thread)


            else:
                log.warn("%s is empty, skipping.", role)
 


    def get_inventory(self):
        """
        Returns the inventory in hosts.yaml
        """
        log.debug("Getting host inventory from %s", self.inventory_path)
        hosts = yaml.load(open(self.inventory_path, 'r'))
        return hosts
