#!/usr/bin/env python3
"""Generates Vagrantfile generation script for a single-node DCOS cluster.

All needed DCOS packages are uploaded to AWS, so the bits are useable without
seeing / touching the dcos-image repository.

Use cases:
1) Local dcos-image dev (Do a local build, make a vagrant using it, launch)
2) Generate a make_vagrant script which can be shipped to customers to launch
   basic vagrant clusters"""

from pkg_resources import resource_string

import gen.template
import providers.util as util


def make_vagrant(gen_out):
    cloud_config = gen_out.templates['cloud-config']
    cloud_config = gen_out.utils.add_services(cloud_config)
    cloud_config = gen_out.utils.add_roles(cloud_config, ['master', 'slave', 'vagrant'])

    vagrant_script = gen.template.parse_resources('vagrant/make_dcos_vagrant.sh.in').render({
        'user_data_body': gen_out.utils.render_cloudconfig(cloud_config),
        'vagrantfile_body': resource_string('gen', 'vagrant/Vagrantfile').decode(),
        'config_body': resource_string('gen', 'vagrant/config.rb').decode(),
        'dcos_image_commit': util.dcos_image_commit,
        'template_generation_date': util.template_generation_date
        })

    return vagrant_script


def do_create(tag, repo_channel_path, channel_commit_path, commit, gen_arguments):
    gen_options = gen.get_options_object()
    gen_arguments['master_discovery'] = 'static'
    gen_arguments['master_list'] = '["127.0.0.1"]'

    gen_out = gen.generate(
        options=gen_options,
        mixins=['vagrant', 'coreos'],
        arguments=gen_arguments,
        cc_package_files=['/etc/mesos-master-provider']
        )

    vagrant_script = make_vagrant(gen_out)

    return {
        'packages': util.cluster_to_extra_packages(gen_out.cluster_packages),
        'artifacts': [
            {
                'channel_path': 'make_dcos_vagrant.sh',
                'local_content': vagrant_script,
                'content_type': 'application/x-sh; charset=utf-8'
            }
        ]
    }
