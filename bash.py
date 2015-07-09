#!/usr/bin/env python3
"""Bash script DCOS integration

Generates a bash script that you provide a list of roles to. Run the bash script
on hosts with the correct roles and DCOS will be installed."""

import argparse
import jinja2
from pkgpanda.util import write_string

import gen
import util
from aws import session_prod, upload_packages

jinja_env = jinja2.Environment(
        undefined=jinja2.StrictUndefined)

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
#   dcos image commit: {{ dcos_image_commit }}
#   generation date: {{ generation_date }}
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

# Set DCOS roles
for role in "$@"
do
    touch "/etc/mesosphere/roles/$role"
done

# Set DCOS machine configuration
{setup_flags}

# Install the DCOS services, start DCOS
{setup_services}"""


def do_bash(options):
    bootstrap_id = util.get_local_build(options.skip_build)

    results = gen.generate(
        options=options,
        mixins=['bash', 'centos', 'onprem'],
        arguments={'bootstrap_id': bootstrap_id},
        extra_cluster_packages=['onprem-config']
        )

    # Reformat the cloud-config into bash heredocs
    # Assert the cloud-config is only write_files
    setup_flags = ""
    cloud_config = results.templates['cloud-config']
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
    for service in results.templates['dcos-services']:
        setup_services += file_template.format(
            filename='/etc/systemd/system/{}'.format(service['name']),
            content=service['content'],
            mode='644',
            owner='root',
            group='root'
            )

    setup_services += "\n"

    # Start, enable services which request it.
    print(results.templates['dcos-services'])
    for service in results.templates['dcos-services']:
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

    # Upload the packages
    bucket = session_prod.resource('s3').Bucket('downloads.mesosphere.io')
    upload_packages(bucket, results.arguments['release_name'], bootstrap_id, results.cluster_packages)

    # Output the dcos install script
    write_string('dcos_install.sh', bash_script)
    print()
    print()
    print("Dcos install script: dcos_install.sh")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='BASH template creation.')
    parser.add_argument('--skip-build', action='store_true')
    gen.add_arguments(parser)
    options = parser.parse_args()
    do_bash(options)
