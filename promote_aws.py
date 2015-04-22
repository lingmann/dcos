#!/usr/bin/env python3
"""
Usage:
  promote_aws <testing_name> <production_name>

Promtion steps:
1) Generate new landing page
2) Download, edit cloudformation templates
3) s3 copy across individual packages
4) upload
    - active.json
    - cloudformation template
    - landing page
    - bootstrap.tar.xz
"""

import urllib.parse
from docopt import docopt
from pkgpanda import PackageId
from pkgpanda.util import load_json, write_json, write_string
from jinja2 import Environment, FileSystemLoader

from util import bucket, render_markdown_data, upload_s3

env = Environment(loader=FileSystemLoader('providers/aws/templates/'))
landing_template = env.get_template("production.md")


def download_s3(obj, out_file):
    body = obj.get()['Body']
    with open(out_file, 'wb') as dest:
        for chunk in iter(lambda: body.read(4096), b''):
            dest.write(chunk)


def main():
    arguments = docopt(__doc__)
    name = arguments['<production_name>']
    testing_name = arguments['<testing_name>']

    def fetch_from_s3(name, target):
        download_s3(
            bucket.Object('dcos/testing/{}/{}'.format(testing_name, name)),
            target
            )

    aws_landing = landing_template.render({
            'regions': [
                'us-west-1',
                'us-west-2',
                'us-east-1',
                'sa-east-1',
                'eu-west-1',
                'eu-central-1',
                'ap-northeast-1',
                'ap-southeast-1',
                'ap-southeast-2'
                ],
            'name': name
        })

    # Generate new landing page
    write_string('prod.aws.html', render_markdown_data(aws_landing))

    # Download, edit cloudformation templates
    fetch_from_s3('simple.cloudformation.json', 'prod.simple.cloudformation.json.in')

    cloudformation = load_json('prod.simple.cloudformation.json.in')
    cloudformation['Mappings']['Parameters']['BootstrapRepoRoot']['default'] = \
        'http://downloads.mesosphere.io/dcos/{}'.format(name)

    write_json('prod.simple.cloudformation.json', cloudformation)

    print("Deploying individual packages")

    def copy_across(path, no_cache=None):
        print("Copying across {}".format(path))
        old_path = urllib.parse.quote('/downloads.mesosphere.io/dcos/testing/{}/{}'.format(
            testing_name, path))

        new_object = bucket.Object('dcos/{}/{}'.format(name, path))

        if no_cache:
            new_object.copy_from(CopySource=old_path, CacheControl='no-cache')
        else:
            new_object.copy_from(CopySource=old_path)

    # Copy across packages
    fetch_from_s3('config/active.json', 'prod.active.json')
    for pkg_id_str in load_json('prod.active.json'):
        pkg_id = PackageId(pkg_id_str)

        pkg_path = 'packages/{}/{}.tar.xz'.format(pkg_id.name, pkg_id_str)
        copy_across(pkg_path)

    # TODO(cmaloney): Should show a temporary interstatial while the next couple
    # steps complete since things are going to be inconsistent.
    # Copy across active.json, bootstrap.tar.xz
    # TODO(cmaloney): Figure out ideal cache settings for these
    copy_across('config/active.json', no_cache=True)
    copy_across('bootstrap.tar.xz', no_cache=True)

    # Upload cloudformation template, new landing page
    upload_s3(
        name,
        'prod.simple.cloudformation.json',
        'simple.cloudformation.json',
        args={'ContentType': 'text/json'},
        no_cache=True)
    upload_s3(
        name,
        'prod.aws.html',
        'aws.html',
        args={'ContentType': 'text/html'},
        no_cache=True)

    print("Ready to launch a cluster:")
    print("https://downloads.mesosphere.io/dcos/{}/aws.html".format(name))


if __name__ == '__main__':
    main()
