#!/usr/bin/env python3
"""Make a vagrant DCOS cluster

Usage:
  make_cluster <name>

"""

import jinja2
import os
import uuid
from docopt import docopt
from subprocess import check_call, check_output

# NOTE: Strict undefined behavior since we're doing generation / validation here.
env = jinja2.Environment(loader=jinja2.FileSystemLoader(os.getcwd()), undefined=jinja2.StrictUndefined)
userdata_template = env.get_template('user-data.jinja')

if __name__ == '__main__':
    arguments = docopt(__doc__)
    cluster_name = arguments['<name>']

    # Generate a pseudo-random s3 bucket name
    aws_s3_prefix = '/dcos-vagrant/{}/{}'.format(cluster_name, uuid.uuid1())

    # Get aws access, secret key
    def get_aws_param(name):
        return check_output(['aws', 'configure', 'get', name]).decode('utf-8').strip()

    aws_secret_key_id = get_aws_param('aws_access_key_id')
    aws_secret_access_key = get_aws_param('aws_secret_access_key')
    # Prompt for AWS access, secret key

    userdata = userdata_template.render({
        'cluster_name': cluster_name,
        'aws_s3_prefix': aws_s3_prefix,
        'aws_secret_key_id': aws_secret_key_id,
        'aws_secret_access_key': aws_secret_access_key
        })

    # Make folder for the cluster-specific files
    check_call(['mkdir', cluster_name])

    # Copy files in
    check_call(['ln', '-s', '{}/Vagrantfile'.format(os.getcwd()), '{}/Vagrantfile'.format(cluster_name)])
    check_call(['ln', '-s', '{}/config.rb'.format(os.getcwd()), '{}/config.rb'.format(cluster_name)])

    with open('{}/user-data'.format(cluster_name), 'w') as f:
        f.write(userdata)

    print("Vagrant cluster ready to launch.")
    print("Launch with:")
    print("$cd {}; vagrant up".format(cluster_name))
