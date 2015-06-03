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
from pkgpanda.util import load_json, load_string
from subprocess import check_call

from util import render_markdown, upload_s3


def main():
    arguments = docopt(__doc__)

    name = "testing/{}".format(arguments['<name>'])

    if not arguments['--skip-mkpanda']:
        # Build all the packages
        check_call(['mkpanda', 'tree', '--mkbootstrap'], cwd='packages')

    # Get the last bootstrap build version
    last_bootstrap = load_string('packages/bootstrap.latest')

    # Build aws cloudformation
    check_call([
        './gen.py',
        'https://s3.amazonaws.com/downloads.mesosphere.io/dcos/',
        name,
        '--bootstrap-id={}'.format(last_bootstrap)
        ], cwd='providers')
    # Upload to s3 bucket
    if not arguments['--skip-package-upload']:
        # Upload packages
        for id_str in load_json('packages/{}.active.json'.format(last_bootstrap)):
            id = PackageId(id_str)
            upload_s3(name, 'packages/{name}/{id}.tar.xz'.format(name=id.name, id=id_str))

        # Upload bootstrap
        upload_s3(
                name,
                'packages/{}.bootstrap.tar.xz'.format(last_bootstrap),
                'bootstrap/{}.bootstrap.tar.xz'.format(last_bootstrap),
                no_cache=True)
        upload_s3(
                name,
                'packages/{}.active.json'.format(last_bootstrap),
                'config/{}.active.json'.format(last_bootstrap),
                no_cache=True)
        upload_s3(
                name,
                'packages/bootstrap.latest',
                'bootstrap.latest',
                no_cache=True)

    # Upload CloudFormation
    upload_s3(name, 'providers/cloudformation.json', 'cloudformation.json', no_cache=True)
    upload_s3(
        name,
        'providers/single-master.cloudformation.json',
        'single-master.cloudformation.json',
        no_cache=True)
    upload_s3(name, 'providers/multi-master.cloudformation.json', 'multi-master.cloudformation.json', no_cache=True)
    upload_s3(name, 'providers/testcluster.cloudformation.json', 'testcluster.cloudformation.json', no_cache=True)
    with open('aws.html', 'w+') as f:
        f.write(render_markdown('providers/aws.md'))
    upload_s3(name, 'aws.html', args={'ContentType': 'text/html'}, no_cache=True)

    print("Performing basic tests")
    for template in ['single-master.', 'multi-master.', '', 'testcluster.']:
        print("Checking template {}cloudformation.json".format(template))
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
