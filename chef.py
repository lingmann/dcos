#!/usr/bin/env python3
"""Generates a chef cookbook for installing DCOS On-Prem"""

import argparse
import yaml
from pkgpanda.util import load_string

import gen
import util


chef_file_template = """file '{filename}' do
    atomic_update true
    content <<EOF
{content}
EOF
    mode '{mode}'
    owner '{owner}'
    group '{group}'
end
"""

default_recipe = """# Cookbook Name:: dcos
# Recipe:: default
#
# TODO(cmaloney): Copyright + License string
# TODO(cmaloney): Force install / requiring dependencies
# - Docker, perf, etc.
service 'docker' do
  action [:start, :enable]
end
# Configure dcos-setup
directory '/etc/mesosphere'
directory '/etc/mesosphere/roles'
node['dcos']['roles'].each do |role|
  file "/etc/mesosphere/roles/#{{role}}" do
    action :create
  end
end
directory '/etc/mesosphere/setup-flags'
{chef_setup_flags}
# Write out dcos services, start them.
{chef_dcos_setup_services}

# Wait for machine to come up
execute 'wait for leader' do
  command 'ping -c 1 leader.mesos'
  retries 1800
  retry_delay 1
end
log 'dcos-started' do
  message 'DCOS node initialized successfully'
end
"""


def make_chef(gen_out):
    # Reformat the cloud-config into chef_cloud_config_files.
    # Assert the cloud-config is only write_files
    chef_cloud_config_files = ""
    cloud_config = gen_out.templates['cloud-config']
    assert len(cloud_config) == 1
    for file_dict in cloud_config['write_files']:
        # NOTE: setup-packages is explicitly disallowed. Should all be in extra
        # cluster packages.
        assert 'setup-packages' not in file_dict['path']
        chef_cloud_config_files += chef_file_template.format(
            filename=file_dict['path'],
            content=file_dict['content'],
            mode=oct(file_dict.get('permissions', 0o644))[2:],
            owner=file_dict.get('owner', 'root'),
            group=file_dict.get('group', 'root')
            )

    # Grab the DCOS services and reformat them into chef_dcos_setup_services
    # Write out the units as files
    chef_services = ""
    for service in gen_out.templates['dcos-services']:
        chef_services += chef_file_template.format(
            filename='/etc/systemd/system/{}'.format(service['name']),
            content=service['content'],
            mode='644',
            owner='root',
            group='root'
            )
    # Start, enable services which request it.
    for service in gen_out.templates['dcos-services']:
        assert service['name'].endswith('.service')
        name = service['name'][:-8]
        if service.get('enable'):
            chef_services += "execute 'systemctl enable {}'\n".format(name)
        if service.get('command') == 'start':
            chef_services += "execute 'systemctl start {}'\n".format(name)

    # Get the general chef files
    chef_files = yaml.load(util.jinja_env.from_string(load_string('gen/chef/chef.yaml')).render({
        'dcos_image_commit': util.dcos_image_commit,
        'generation_date': util.template_generation_date,
        'distro': 'centos'
    }))

    chef_files['write_files'].append({
        'path': 'recipes/default.rb',
        'content': default_recipe.format(
            chef_setup_flags=chef_cloud_config_files,
            chef_dcos_setup_services=chef_services
            )
        })

    # TODO(cmaloney): Test the chef using kitchen?

    # Turn the chef files into a tarball to email to customers
    chef_tarball = 'chef-{}.tar.xz'.format(gen_out.arguments['config_id'])

    gen.do_gen_package(chef_files, chef_tarball)

    return chef_tarball


def do_chef_only(options):
    gen_out = gen.generate(
        options=options,
        mixins=['chef', 'centos', 'onprem'],
        extra_cluster_packages=['onprem-config']
        )
    chef_tarball = make_chef(gen_out)
    util.do_bundle_onprem([chef_tarball], gen_out, options.output_dir)
    print("Chef tarball:", chef_tarball)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Gen Chef templates to use to install a DCOS cluster')

    # No subcommand
    gen.add_arguments(parser)
    parser.add_argument('--output-dir',
                        type=str,
                        help='Directory to write generated config')
    do_chef_only(parser.parse_args())
