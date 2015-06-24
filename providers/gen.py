#!/usr/bin/env python3
"""Generate provider-specific templates, data.
Usage:
gen.py [aws|testcluster] <base_url> <release_name> --bootstrap-id=<bootstrap_id>
gen.py vagrant <release_name> <cluster_name> [--copy] [--bootstrap-id=<bootstrap_id>]
"""

from datetime import datetime
import json
import os
import sys
import urllib.request
from docopt import docopt
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from string import Template
from subprocess import check_output

import aws
import vagrant



def write_json(filename, data):
    with open(filename, "w+") as f:
        return json.dump(data, f)


def write_string(filename, data):
    with open(filename, "w+") as f:
        return f.write(data)


# NOTE: Strict undefined behavior since we're doing generation / validation here.
env = Environment(loader=FileSystemLoader('templates'), undefined=StrictUndefined)
cc_template = env.get_template('cloud-config.yaml')


def render_cloudconfig_base(paramters, bootstrap_id):
    assert type(paramters.resolvers) == list
    assert bootstrap_id
    return cc_template.render({
        'bootstrap_id': bootstrap_id,
        'bootstrap_url': paramters.GetParameter('bootstrap_url'),
        'roles': paramters.roles,
        'master_quorum': paramters.GetParameter('master_quorum'),
        'extra_files': paramters.extra_files,
        'stack_name': paramters.GetParameter('stack_name'),
        'early_units': paramters.early_units,
        'config_writer': paramters.config_writer,
        'resolvers': paramters.GetParameter('fallback_dns'),
        'late_units': paramters.late_units,
        })


# TODO(cmaloney): Minimize amount of code in this function. All
# providers should be as simple as possible.
def gen_aws(name, bootstrap_url, render_cloudconfig):

    # TODO(cmaloney): That we talk about 'testcluster' here is wrong.
    # We should just talk about 'extra parameters'.
    def aws_cloudformation(simple, testcluster=False):

        return aws.render_cloudformation(
            simple,
            render_cloudconfig(get_params(['master'])),
            render_cloudconfig(get_params(['slave'])),
            render_cloudconfig(get_params(['slave_public'])),
            bootstrap_url,
            testcluster,
            dcos_image_commit,
            template_generation_date
            )

    # Parameterized / custom template.
    write_string('cloudformation.json', aws_cloudformation(False))
    write_string('testcluster.cloudformation.json', aws_cloudformation(False, True))

    # Simple template.
    single_master_cf = aws_cloudformation(True)
    write_string('single-master.cloudformation.json', single_master_cf)

    # Simple 3 master.
    # Transform 1-master into having 3 masters in the scaling group.
    cf_multimaster = json.loads(single_master_cf)
    cf_multimaster['Mappings']['Parameters']['MasterQuorumCount']['default'] = 2
    cf_multimaster['Mappings']['Parameters']['MasterInstanceCount']['default'] = 3
    write_json('multi-master.cloudformation.json', cf_multimaster)

    # Create the aws launch button page
    write_string('aws.md', aws.render_buttons(name))


def main():
    arguments = docopt(__doc__)

    release_name = arguments['<release_name>']

    if not arguments['--bootstrap-id']:
        # Download the bootstrap id
        url = 'http://downloads.mesosphere.com/dcos/{}/bootstrap.latest'.format(release_name)
        arguments['--bootstrap-id'] = urllib.request.urlopen(url).read().decode('utf-8')

    def render_cloudconfig(parameters):
        return render_cloudconfig_base(parameters, arguments['--bootstrap-id'].strip())

    # Name shouldn't start or end with '/'
    assert release_name[0] != '/'
    assert release_name[-1] != '/'

    if arguments['vagrant']:
        vagrant.gen(
            arguments['<release_name>'],
            arguments['<cluster_name>'],
            render_cloudconfig,
            arguments['--copy'])
        sys.exit(0)

    base_url = arguments['<base_url>']

    # TODO(cmaloney): Make more human error messages
    # base_url must end in '/'
    assert base_url[-1] == '/'

    bootstrap_url = base_url + release_name
    gen_aws(release_name, bootstrap_url, render_cloudconfig)

if __name__ == '__main__':
    main()
