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
2) Push individual packages to custom directory
3) Push active.json to custom directory
4) Push bootstrap.tar.xz
2) Push individual packages up
3) Push active.json up
4) Push bootstrap.tar.xz up
"""

import boto3
import requests
from docopt import docopt
from pkgpanda import PackageId
from pkgpanda.util import load_json
from subprocess import check_call

s3 = boto3.resource('s3')
bucket = s3.Bucket('downloads.mesosphere.io')


def upload_s3(name, path, dest_path=None, args={}, no_cache=False):
    if no_cache:
        args['CacheControl'] = 'no-cache'

    with open(path, 'rb') as data:
        print("Uploading {}{}".format(path, " as {}".format(dest_path) if dest_path else ''))
        if not dest_path:
            dest_path = path
        return bucket.Object('dcos/testing/{name}/{path}'.format(name=name, path=dest_path)).put(Body=data, **args)


def upload_packages(name):
    # List packages from active.json, upload them all
    for id_str in load_json('packages/active.json'):
        id = PackageId(id_str)
        upload_s3(name, 'packages/{name}/{id}.tar.xz'.format(name=id.name, id=id_str))


def main():
    arguments = docopt(__doc__)

    name = arguments['<name>']

    if not arguments['--skip-mkpanda']:
        # Build all the packages
        check_call(['mkpanda', 'tree', '--mkbootstrap'], cwd='packages')

    # Build aws cloudformation
    check_call([
        './gen_aws.py',
        'http://s3.amazonaws.com/downloads.mesosphere.io/dcos/',
        "testing/{}".format(name)
        ], cwd='providers/aws')
    # Upload to s3 bucket
    if not arguments['--skip-package-upload']:
        upload_packages(name)
        # Upload bootstrap
        upload_s3(name, 'packages/bootstrap.tar.xz', 'bootstrap.tar.xz', no_cache=True)
        upload_s3(name, 'packages/active.json', 'config/active.json', no_cache=True)
    # Upload CloudFormation
    upload_s3(name, 'providers/aws/cloudformation.json', 'cloudformation.json', no_cache=True)
    upload_s3(name, 'providers/aws/simple.cloudformation.json', 'simple.cloudformation.json', no_cache=True)
    with open('aws.html', 'w+') as f:
        f.write(requests.post(
            "https://api.github.com/markdown/raw",
            headers={'Content-type': 'text/plain'},
            data=open('providers/aws/launch_buttons.md')
            ).text)
    upload_s3(name, 'aws.html', args={'ContentType': 'text/html'}, no_cache=True)

    print("Ready to launch a cluster:")
    print("http://s3.amazonaws.com/downloads.mesosphere.io/dcos/testing/{}/aws.html".format(name))

if __name__ == '__main__':
    main()
