#!/usr/bin/env python3
"""Vagrantfile Creation.

Generates Vagrantfile + helper script.

All needed DCOS packages are uploaded to AWS, so the bits are useable without
seeing / touching the dcos-image repository

Use cases:
1) Local dcos-image dev (Do a local build, make a vagrant using it, launch)
2) Generate a make_vagrant script which can be shipped to customers to launch
   basic vagrant clusters

"""

import argparse
import jinja2

import gen
import util
from aws import session_prod, upload_packages, upload_string

jinja_env = jinja2.Environment(
        undefined=jinja2.StrictUndefined)


def do_vagrant(options):
    bootstrap_id = util.get_local_build(options.skip_build)

    results = gen.generate(
        options=options,
        mixins=['vagrant', 'coreos'],
        arguments={'bootstrap_id': bootstrap_id}
        )

    cloud_config = results.templates['cloud-config']
    cloud_config = results.utils.add_services(cloud_config)
    cloud_config = results.utils.add_roles(cloud_config, ['master', 'slave', 'vagrant'])

    vagrant_script = jinja_env.from_string(open('gen/vagrant/make_vagrant').read()).render({
        'user_data_body': results.utils.render_cloudconfig(cloud_config),
        'vagrantfile_body': open('gen/vagrant/Vagrantfile').read(),
        'config_body': open('gen/vagrant/config.rb').read(),
        'dcos_image_commit': util.dcos_image_commit,
        'template_generation_date': util.template_generation_date
        })

    # Upload the packages, make_dcos_vagrant script
    bucket = session_prod.resource('s3').Bucket('downloads.mesosphere.io')
    upload_packages(bucket, results.arguments['release_name'], bootstrap_id, results.arguments['config_package_id'])

    # Upload the vagrant script
    obj = upload_string(
            bucket,
            results.arguments['release_name'],
            'make_dcos_vagrant.sh',
            vagrant_script,
            {
                'CacheControl': 'no-cache',
                'ContentType': 'application/x-sh; charset=utf-8',
            })
    print("Vagrant available at: https://downloads.mesosphere.com/{}".format(obj.key))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Vagrantfile template creation.')
    parser.add_argument('--skip-build', action='store_true')
    gen.add_arguments(parser)
    options = parser.parse_args()
    do_vagrant(options)
