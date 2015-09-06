#!/usr/bin/env python3
"""Generates Vagrantfile generation script for a single-node DCOS cluster.

All needed DCOS packages are uploaded to AWS, so the bits are useable without
seeing / touching the dcos-image repository.

Use cases:
1) Local dcos-image dev (Do a local build, make a vagrant using it, launch)
2) Generate a make_vagrant script which can be shipped to customers to launch
   basic vagrant clusters"""

import gen
import util


def make_vagrant(gen_out):
    cloud_config = gen_out.templates['cloud-config']
    cloud_config = gen_out.utils.add_services(cloud_config)
    cloud_config = gen_out.utils.add_roles(cloud_config, ['master', 'slave', 'vagrant'])

    vagrant_script = util.jinja_env.from_string(open('gen/vagrant/make_vagrant').read()).render({
        'user_data_body': gen_out.utils.render_cloudconfig(cloud_config),
        'vagrantfile_body': open('gen/vagrant/Vagrantfile').read(),
        'config_body': open('gen/vagrant/config.rb').read(),
        'dcos_image_commit': util.dcos_image_commit,
        'template_generation_date': util.template_generation_date
        })

    return vagrant_script


def do_create(tag, channel, commit, gen_arguments):
    gen_options = gen.get_options_object()
    gen_out = gen.generate(
        options=gen_options,
        mixins=['vagrant', 'coreos'],
        arguments=gen_arguments
        )

    vagrant_script = make_vagrant(gen_out)

    return {
        'extra_packages': util.cluster_to_extra_packages(gen_out.cluster_packages),
        'files': [
            {
                'known_path': 'make_dcos_vagrant.sh',
                'stable_path': 'make_vagrant/{}.sh'.format(gen_out.arguments['config_id']),
                'content': vagrant_script,
                'upload_args': {
                    'ContentType': 'application/x-sh; charset=utf-8'
                }
            }
        ]
    }
