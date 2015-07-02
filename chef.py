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
import yaml
from pkgpanda.util import load_string

import gen
import util
from aws import session_prod, upload_packages

jinja_env = jinja2.Environment(
        undefined=jinja2.StrictUndefined)

chef_file_template = """file '{filename}' do
    atomic_update true
    content <<EOF
{content}EOF
    mode '{mode}'
    owner '{owner}'
    group '{group}'
done
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
directory '/etc/mesosphere/roles'
node['dcos']['roles'].each do |role|
  file "/etc/mesosphere/roles/#{{role}}" do
    action :create
  end
end
directory '/etc/mesosphere/setup-flags'
{chef_setup_flags}
# Write out dcos services
{chef_dcos_setup_services}
# Start DCOS on the machine
execute 'systemctl enable dcos-setup'
execute 'systemctl start dcos-setup'
execute 'wait for leader' do
  command 'ping -c 1 leader.mesos'
  retries 1800
  retry_delay 1
end
log 'dcos-started' do
  message 'DCOS node initialized successfully'
end
"""


def do_chef(options):
    bootstrap_id = util.get_local_build(options.skip_build)

    results = gen.generate(
        options=options,
        mixins=['chef', 'centos', 'onprem'],
        arguments={'bootstrap_id': bootstrap_id},
        extra_cluster_packages=['onprem-config']
        )

    # Reformat the cloud-config into chef_cloud_config_files.
    # Assert the cloud-config is only write_files
    chef_cloud_config_files = ""
    cloud_config = results.templates['cloud-config']
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
    for service in results.templates['dcos-services']:
        chef_services += chef_file_template.format(
            filename='/etc/systemd/system/{}'.format(service['name']),
            content=service['content'],
            mode='644',
            owner='root',
            group='root'
            )
    # Start, enable services which request it.
    for service in results.templates['dcos-services']:
        assert service['name'].endswith('.service')
        name = service['name'][:-8]
        if service.get('enable'):
            chef_services += "execute 'systemctl enable {}'\n".format(name)
        if service.get('start'):
            chef_services += "execute 'systemctl start {}'\n".format(name)

    # Get the general chef files
    chef_files = yaml.load(jinja_env.from_string(load_string('gen/chef/chef.yaml')).render({
        'version': util.dcos_image_commit,
        'distro': 'centos'
    }))

    chef_files['write_files'].append({
        'path': 'recipies/default.rb',
        'content': default_recipe.format(
            chef_setup_flags=chef_cloud_config_files,
            chef_dcos_setup_services=chef_services
            )
        })

    # TODO(cmaloney): Test the chef using kitchen?

    # Turn the chef files into a tarball to email to customers
    gen.do_gen_package(chef_files, 'chef-{}.tar.xz'.format(results.arguments['config_id']))

    # Upload the packages, make_dcos_vagrant script
    bucket = session_prod.resource('s3').Bucket('downloads.mesosphere.io')
    upload_packages(bucket, results.arguments['release_name'], bootstrap_id, results.cluster_packages)
#
#    # Upload the vagrant script
#    obj = upload_string(
#            bucket,
#            results.arguments['release_name'],
#            'make_dcos_vagrant.sh',
#            vagrant_script,
#            {
#                'CacheControl': 'no-cache',
#                'ContentType': 'application/x-sh; charset=utf-8',
#            })
#    print("Vagrant available at: https://downloads.mesosphere.com/{}".format(obj.key))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Chef template creation.')
    parser.add_argument('--skip-build', action='store_true')
    gen.add_arguments(parser)
    options = parser.parse_args()
    do_chef(options)
