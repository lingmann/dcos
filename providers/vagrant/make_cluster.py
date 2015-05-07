#!/usr/bin/env python3
"""Make a vagrant DCOS cluster

Usage:
  make_cluster [ --copy ] <release_name> <cluster_name>

Options:
  --copy    Copy files instead of symlinking
"""

import jinja2
import os
import shutil
from docopt import docopt
from subprocess import check_call

# NOTE: Strict undefined behavior since we're doing generation / validation here.
env = jinja2.Environment(loader=jinja2.FileSystemLoader(os.getcwd()),
                         undefined=jinja2.StrictUndefined)
userdata_template = env.get_template('user-data.jinja')

if __name__ == '__main__':
    arguments = docopt(__doc__)
    cluster_name = arguments['<cluster_name>']
    release_name = arguments['<release_name>']

    userdata = userdata_template.render({
        'cluster_name': cluster_name,
        'release_name': release_name
        })

    # Make folder for the cluster-specific files
    check_call(['mkdir', cluster_name])

    # Copy files in
    copy = os.symlink
    if arguments['--copy']:
        copy = shutil.copyfile
    copy('{}/Vagrantfile'.format(os.getcwd()), '{}/Vagrantfile'.format(cluster_name))
    copy('{}/config.rb'.format(os.getcwd()), '{}/config.rb'.format(cluster_name))

    with open('{}/user-data'.format(cluster_name), 'w') as f:
        f.write(userdata)

    print("Vagrant cluster ready to launch.")
    print("Launch with:")
    print("$ cd {}; vagrant up".format(cluster_name))
