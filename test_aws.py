#!/usr/bin/env python3
"""simple end to end test of building everything -> AWS Cluster.

Usage:
    test_aws <name> [--skip-build] [--skip-upload] [--skip-launch] [--skip-gen]
    test_aws delete <name>

"""

import os
import sys
from copy import deepcopy
from docopt import docopt
from subprocess import check_call

# TODO(cmaloney): don't shell out for all the steps
base_env = deepcopy(os.environ)

prod_env = deepcopy(os.environ)
prod_env['AWS_PROFILE'] = 'production'

dev_env = deepcopy(os.environ)
dev_env['AWS_PROFILE'] = 'development'


def do_build():
    check_call(['mkpanda', 'tree', '--mkbootstrap'], cwd='packages', env=base_env)


def do_gen():
    check_call([
            './gen.py',
            'aws',
            'coreos',
            '--assume-defaults',
            '--config=aws/1master.config.json'
        ],
        cwd='setup',
        env=base_env)


def do_launch(name):
    check_call(['./setup/aws/util/cluster.py', 'launch', name, 'setup/cloudformation.json'],
               env=dev_env)


def do_upload():
    check_call(['./upload_packages.py', 'testing/cmaloney'], env=prod_env)


def main():
    arguments = docopt(__doc__)

    name = arguments['<name>']

    if arguments['delete']:
        check_call(['./setup/aws/util/cluster.py', 'delete', name],
                   env=dev_env)
        sys.exit(0)

    # Launch a build
    if not arguments['--skip-build']:
        do_build()

    # Gen AWS templates
    if not arguments['--skip-gen']:
        do_gen()

    if not arguments['--skip-upload']:
        do_upload()

    if not arguments['--skip-launch']:
        do_launch(name)


if __name__ == '__main__':
    main()
