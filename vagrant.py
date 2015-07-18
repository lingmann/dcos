#!/usr/bin/env python3
"""Generates Vagrantfile generation script for a single-node DCOS cluster.

All needed DCOS packages are uploaded to AWS, so the bits are useable without
seeing / touching the dcos-image repository.

Use cases:
1) Local dcos-image dev (Do a local build, make a vagrant using it, launch)
2) Generate a make_vagrant script which can be shipped to customers to launch
   basic vagrant clusters"""

import argparse
import jinja2

import gen
import util
from upload import get_bucket, upload_packages, upload_release, upload_string

jinja_env = jinja2.Environment(
        undefined=jinja2.StrictUndefined)


def make_vagrant(gen_out):
    cloud_config = gen_out.templates['cloud-config']
    cloud_config = gen_out.utils.add_services(cloud_config)
    cloud_config = gen_out.utils.add_roles(cloud_config, ['master', 'slave', 'vagrant'])

    vagrant_script = jinja_env.from_string(open('gen/vagrant/make_vagrant').read()).render({
        'user_data_body': gen_out.utils.render_cloudconfig(cloud_config),
        'vagrantfile_body': open('gen/vagrant/Vagrantfile').read(),
        'config_body': open('gen/vagrant/config.rb').read(),
        'dcos_image_commit': util.dcos_image_commit,
        'template_generation_date': util.template_generation_date
        })

    return vagrant_script


def upload_vagrant(release_name, name, script_contents):
    # Upload the vagrant script
    return upload_string(
        release_name,
        name,
        script_contents,
        {
            'CacheControl': 'no-cache',
            'ContentType': 'application/x-sh; charset=utf-8',
        })


def do_vagrant_and_build(options):
    bootstrap_id = util.get_local_build(options.skip_build)
    gen_out = gen.generate(
        options=options,
        mixins=['vagrant', 'coreos'],
        arguments={'bootstrap_id': bootstrap_id}
        )
    vagrant_script = make_vagrant(gen_out)
    upload_release(
        gen_out.arguments['release_name'],
        bootstrap_id,
        util.cluster_to_extra_packages(gen_out.cluster_packages))

    # Upload the vagrant script
    obj = upload_vagrant(
        gen_out.arguments['release_name'],
        '{}.vagrant.sh'.format(gen_out.arguments['config_id']),
        vagrant_script
        )

    print("Vagrant available at: https://downloads.mesosphere.com/{}".format(obj.key))


def do_vagrant_only(options):
    gen_out = gen.generate(
        options=options,
        mixins=['vagrant', 'coreos']
        )
    vagrant_script = make_vagrant(gen_out)

    # Upload the vagrant script
    obj = upload_vagrant(
        gen_out.arguments['release_name'],
        '{}.vagrant.sh'.format(gen_out.arguments['config_id']),
        vagrant_script
        )

    print("Vagrant available at: https://downloads.mesosphere.com/{}".format(obj.key))


def do_vagrant_make_candidate(options):
    release_name = "testing/" + options.candidate_name
    bootstrap_id = util.get_local_build(True)
    gen_out = gen.generate(
        options=options,
        mixins=['vagrant', 'coreos'],
        arguments={
            'release_name': release_name,
            'bootstrap_id': bootstrap_id}
        )
    vagrant_script = make_vagrant(gen_out)

    # Upload the vagrant script
    obj = upload_vagrant(
        release_name,
        'make_dcos_vagrant.sh',
        vagrant_script
        )

    # Upload vagrant-specific packages
    upload_packages(
        get_bucket(),
        release_name,
        util.cluster_to_extra_packages(gen_out.cluster_packages))

    print("Vagrant available at: https://downloads.mesosphere.com/{}".format(obj.key))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Gen Vagrant single-node DCOS cluster generation script')
    subparsers = parser.add_subparsers(title='commands')

    # No subcommand
    gen.add_arguments(parser)
    parser.set_defaults(func=do_vagrant_only)

    # Build subcommand
    build = subparsers.add_parser('build')
    gen.add_arguments(build)
    build.set_defaults(func=do_vagrant_and_build)
    build.add_argument('--skip-build', action='store_true')

    # make_candidate subcommand
    make_candidate = subparsers.add_parser('make_candidate')
    gen.add_arguments(make_candidate)
    make_candidate.set_defaults(func=do_vagrant_make_candidate)
    make_candidate.add_argument('candidate_name')

    # Parse the arguments and dispatch.
    options = parser.parse_args()
    options.func(options)
