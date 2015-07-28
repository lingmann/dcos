#!/usr/bin/env python3
"""Generates a bash script for installing DCOS On-Prem."""

import argparse
from pkgpanda.util import write_string

import gen
import util
from upload import upload_release

file_template = """mkdir -p `dirname {filename}`
cat <<'EOF' > "{filename}"
{content}
EOF
chmod {mode} {filename}

"""

bash_template = """#!/bin/bash
#
# BASH script to install DCOS on a node
#
# Usage:
#
#   dcos_install.sh <role>...
#
#
# Metadata:
#   dcos image commit: {dcos_image_commit}
#   generation date: {generation_date}
#
# TODO(cmaloney): Copyright + License string here

set -o errexit -o nounset -o pipefail

if [ "$#" -lt 1 ]; then
    echo "At least one role must be specified"
    exit 1
fi

if [[ $EUID -ne 0 ]]; then
    echo "This script must be run as root" 1>&2
    exit 1
fi

mkdir -p /etc/mesosphere/roles
mkdir -p /etc/mesosphere/setup-flags

# Set DCOS roles
for role in "$@"
do
    touch "/etc/mesosphere/roles/$role"
done

# Set DCOS machine configuration
{setup_flags}

# Install the DCOS services, start DCOS
{setup_services}"""


def make_bash(gen_out):

    # Reformat the cloud-config into bash heredocs
    # Assert the cloud-config is only write_files
    setup_flags = ""
    cloud_config = gen_out.templates['cloud-config']
    assert len(cloud_config) == 1
    for file_dict in cloud_config['write_files']:
        # NOTE: setup-packages is explicitly disallowed. Should all be in extra
        # cluster packages.
        assert 'setup-packages' not in file_dict['path']
        setup_flags += file_template.format(
            filename=file_dict['path'],
            content=file_dict['content'],
            mode=oct(file_dict.get('permissions', 0o644))[2:],
            owner=file_dict.get('owner', 'root'),
            group=file_dict.get('group', 'root')
            )

    # Reformat the DCOS systemd units to be bash written and started.
    # Write out the units as files
    setup_services = ""
    for service in gen_out.templates['dcos-services']:
        setup_services += file_template.format(
            filename='/etc/systemd/system/{}'.format(service['name']),
            content=service['content'],
            mode='644',
            owner='root',
            group='root'
            )

    setup_services += "\n"

    # Start, enable services which request it.
    for service in gen_out.templates['dcos-services']:
        assert service['name'].endswith('.service')
        name = service['name'][:-8]
        if service.get('enable'):
            setup_services += "systemctl enable {}\n".format(name)
        if service.get('command') == 'start':
            setup_services += "systemctl start {}\n".format(name)

    # Populate in the bash script template
    bash_script = bash_template.format(
        dcos_image_commit=util.dcos_image_commit,
        generation_date=util.template_generation_date,
        setup_flags=setup_flags,
        setup_services=setup_services
        )

    # Output the dcos install script
    write_string('dcos_install.sh', bash_script)

    return 'dcos_install.sh'


def do_bash_and_build(options):
    bootstrap_id = util.get_local_build(options.skip_build)
    gen_out = gen.generate(
        options=options,
        mixins=['bash', 'centos', 'onprem'],
        arguments={'bootstrap_id': bootstrap_id},
        extra_cluster_packages=['onprem-config']
        )
    make_bash(gen_out)
    upload_release(
        gen_out.arguments['release_name'],
        bootstrap_id,
        util.cluster_to_extra_packages(gen_out.cluster_packages)
        )
    print("\n\nDcos install script: dcos_install.sh")


def do_bash_only(options):
    gen_out = gen.generate(
        options=options,
        mixins=['bash', 'centos', 'onprem', 'onprem-exhibitor-fs'],
        extra_cluster_packages=['onprem-config']
        )
    make_bash(gen_out)
    util.do_bundle_onprem(['dcos_install.sh'], gen_out)
    print("\n\nDCOS Install Package: onprem.tar.xz")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Gen BASH templates to use to install a DCOS cluster')
    subparsers = parser.add_subparsers(title='commands')

    # No subcommand
    gen.add_arguments(parser)
    parser.set_defaults(func=do_bash_only)

    # Build subcommand
    build = subparsers.add_parser('build')
    gen.add_arguments(build)
    build.set_defaults(func=do_bash_and_build)
    build.add_argument('--skip-build', action='store_true')

    # Parse the arguments and dispatch.
    options = parser.parse_args()
    options.func(options)
