import subprocess
import os
import logging as log

def test(options):
    process = subprocess.Popen(
        'ssh -i {} {}@10.33.1.20'.format(options.ssh_key_path, ssh_user), 
        shell=True,
        stdout=subprocess.PIPE, 
        stderr=subprocess.STDOUT)
        
    output, stderr = process.communicate()
    status = process.poll()
    print(output)
