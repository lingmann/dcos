#!/usr/bin/env python3
"""Generate provider-specific templates, data.
Usage:
gen.py [aws] <base_url> <name>

"""
import json
from docopt import docopt
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from pkgpanda.util import write_json, write_string

import aws
import aws.cc_chunks

# NOTE: Strict undefined behavior since we're doing generation / validation here.
env = Environment(loader=FileSystemLoader('templates'), undefined=StrictUndefined)
cc_template = env.get_template('cloud-config.yaml')


def render_cloudconfig(roles, master_quorum, master_count, bootstrap_url, provider_cc):
    assert type(roles) == list
    return cc_template.render({
        'bootstrap_url': bootstrap_url,
        'roles': roles,
        'master_quorum': master_quorum,
        'extra_files': provider_cc.extra_files(master_count),
        'stack_name': provider_cc.stack_name,
        'early_units': provider_cc.early_units,
        'config_writer': provider_cc.config_writer,
        'late_units': provider_cc.late_units(roles)
        })


# TODO(cmaloney): Minimize amount of code in this function. All
# providers should be as simple as possible.
def gen_aws(name, bootstrap_url):

    def aws_cloudconfig(roles, simple):
        return render_cloudconfig(
                roles,
                aws.render_parameter(simple, 'MasterQuorumCount'),
                aws.render_parameter(simple, 'MasterInstanceCount'),
                aws.render_parameter(simple, 'BootstrapRepoRoot'),
                aws.cc_chunks)

    def aws_cloudformation(simple):
        return aws.render_cloudformation(
            simple,
            aws_cloudconfig(['master'], simple),
            aws_cloudconfig(['slave'], simple),
            bootstrap_url
            )

    # Parameterized / custom template.
    write_string('cloudformation.json', aws_cloudformation(False))

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

    do_gen_aws = False
    base_url = arguments['<base_url>']
    name = arguments['<name>']

    # TODO(cmaloney): Make more human error messages
    # base_url must end in '/'
    assert base_url[-1] == '/'

    # Name shouldn't start or end with '/'
    assert name[0] != '/'
    assert name[-1] != '/'

    bootstrap_url = base_url + name

    if arguments['aws']:
        do_gen_aws = True
    else:
        do_gen_aws = True

    if do_gen_aws:
        gen_aws(name, bootstrap_url)

if __name__ == '__main__':
    main()
