#!/usr/bin/env python3
"""
Usage:
  deploy_aws <name> [--skip-mkpanda] [--skip-package-upload]

Deploy steps:
1) Build everything
2) Make aws s3 directory for push, upload:
    - individual packages
    - active.json
    - bootstrap.tar.xz
    - CloudFormation template + landing page
"""

from docopt import docopt
from pkgpanda import PackageId
from pkgpanda.util import load_json
from subprocess import check_call

from util import render_markdown, upload_s3


def upload_packages(name):
    # List packages from active.json, upload them all
    for id_str in load_json('packages/active.json'):
        id = PackageId(id_str)
        upload_s3(name, 'packages/{name}/{id}.tar.xz'.format(name=id.name, id=id_str))


def main():
    arguments = docopt(__doc__)

    name = "testing/{}".format(arguments['<name>'])

    if not arguments['--skip-mkpanda']:
        # Build all the packages
        check_call(['mkpanda', 'tree', '--mkbootstrap'], cwd='packages')

    # Build aws cloudformation
    check_call([
        './gen_aws.py',
        'http://s3.amazonaws.com/downloads.mesosphere.io/dcos/',
        name
        ], cwd='providers/aws')
    # Upload to s3 bucket
    if not arguments['--skip-package-upload']:
        upload_packages(name)
        # Upload bootstrap
        upload_s3(name, 'packages/bootstrap.tar.xz', 'bootstrap.tar.xz', no_cache=True)
        upload_s3(name, 'packages/active.json', 'config/active.json', no_cache=True)
    # Upload CloudFormation
    upload_s3(name, 'providers/aws/cloudformation.json', 'cloudformation.json', no_cache=True)
    upload_s3(
        name,
        'providers/aws/single-master.cloudformation.json',
        'single-master.cloudformation.json',
        no_cache=True)
    upload_s3(name, 'providers/aws/multi-master.cloudformation.json', 'multi-master.cloudformation.json', no_cache=True)
    with open('aws.html', 'w+') as f:
        f.write(render_markdown('providers/aws/launch_buttons.md'))
    upload_s3(name, 'aws.html', args={'ContentType': 'text/html'}, no_cache=True)

    print("Performing basic tests")
    for template in ['single-master.', 'multi-master.', '']:
        check_call([
            'aws',
            'cloudformation',
            'validate-template',
            '--template-url',
            'https://s3.amazonaws.com/downloads.mesosphere.io/dcos/'
                + name + '/' + template + 'cloudformation.json'])

    print("Ready to launch a cluster:")
    print("http://s3.amazonaws.com/downloads.mesosphere.io/dcos/{}/aws.html".format(name))

if __name__ == '__main__':
    main()
