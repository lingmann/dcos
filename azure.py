#!/usr/bin/env python3
"""Azure Image Creation, Management, Testing"""

import argparse
import json
import re
import sys
import yaml
from copy import deepcopy

import gen
import util


late_services = """- name: dcos-cfn-signal.service
  command: start
  content: |
    [Unit]
    Description=Signal CloudFormation Success
    After=dcos.target
    Requires=dcos.target
    ConditionPathExists=!/var/lib/dcos-cfn-signal
    [Service]
    Type=simple
    Restart=on-failure
    StartLimitInterval=0
    RestartSec=15s
    ExecStartPre=/usr/bin/docker pull mbabineau/cfn-bootstrap
    ExecStartPre=/bin/ping -c1 leader.mesos
    ExecStartPre=/usr/bin/docker run --rm mbabineau/cfn-bootstrap \\
      cfn-signal -e 0 \\
      --resource {{ report_name }} \\
      --stack { "Ref": "AWS::StackName" } \\
      --region { "Ref" : "AWS::Region" }
    ExecStart=/usr/bin/touch /var/lib/dcos-cfn-signal"""

cf_instance_groups = {
    'master': {
        'report_name': 'MasterServerGroup',
        'roles': ['master', 'aws_master']
    },
    'slave': {
        'report_name': 'SlaveServerGroup',
        'roles': ['slave']
    }
}

AWS_REF_REGEX = re.compile(r"(?P<before>.*)(?P<ref>{ .* })(?P<after>.*)")


# TODO(mj): Use RPC if Azure supports it
def validate_cloud_config(cc_string):
    """Check for any invalid characters in the cloud config, and exit with an
    error message if any invalid characters are detected."""
    illegal_pattern = re.compile("[']")
    illegal_match = illegal_pattern.search(cc_string)
    if illegal_match:
        print("ERROR: Illegal cloud config string detected.", file=sys.stderr)
        print("ERROR: {} matches pattern {}".format(
            illegal_match.string, illegal_match.re), file=sys.stderr)
        sys.exit(1)


# TODO(mj): update, add return
def transform(line):
    prevend = 0
    for m in re.finditer('(?P<pre>.*?)\[\[\[(?P<inject>.*?)\]\]\]', j):
        before = m.group('pre')
        validate_cloud_config(before)
        param = m.group('inject')
        print("'{}', {},".format(before, param), end='')
        prevend = m.end()

    print("[base64(concat('#cloud-config\n\n', ", end='')
    validate_cloud_config(j[prevend:])
    print("'{}'))]".format(j[prevend:]), end='')


def render_cloudformation(
        # default CF template with some preset parameters already (calc.py) replaced
        cf_template,
        master_cloudconfig,
        slave_cloudconfig):
    # TODO(cmaloney): There has to be a cleaner way to do this transformation.
    # For now just moved from cloud_config_cf.py
    # TODO(cmaloney): Move with the logic that does this same thing in Azure
    def transform_lines(text):
        return ''.join(map(transform, text.splitlines())).rstrip(',\n')

    print(cf_template)
    template_str = util.jinja_env.from_string(cf_template).render({
        'master_cloud_config': transform_lines(master_cloudconfig),
        'slave_cloud_config': transform_lines(slave_cloudconfig)
    })

    print(template_str)
    template_json = json.loads(template_str)

    template_json['Metadata']['DcosImageCommit'] = util.dcos_image_commit
    template_json['Metadata']['TemplateGenerationDate'] = util.template_generation_date

    return json.dumps(template_json)


def gen_templates(arguments, options):
    results = gen.generate(
        options=options,
        # mounting drive, disable etcd
        mixins=['aws', 'coreos', 'coreos-aws'],
        # jinja template
        extra_templates={'cloudformation': ['gen/aws/templates/cloudformation.json']},
        arguments=arguments
        )

    cloud_config = results.templates['cloud-config']

    # Add general services
    cloud_config = results.utils.add_services(cloud_config)

    # Specialize for master, slave, slave_public
    variant_cloudconfig = {}
    for variant, params in cf_instance_groups.items():
        cc_variant = deepcopy(cloud_config)

        # Specialize the dcos-cfn-signal service
        cc_variant = results.utils.add_units(
            cc_variant,
            yaml.load(util.jinja_env.from_string(late_services).render(params)))

        # Add roles
        cc_variant = results.utils.add_roles(cc_variant, params['roles'] + ['aws'])

        # NOTE: If this gets printed in string stylerather than '|' the AWS
        # parameters which need to be split out for the cloudformation to
        # interpret end up all escaped and undoing it would be hard.
        variant_cloudconfig[variant] = results.utils.render_cloudconfig(cc_variant)

    # Render the cloudformation
    cloudformation = render_cloudformation(
        results.templates['cloudformation'],
        variant_cloudconfig['master'],
        variant_cloudconfig['slave']
        )

    return gen.Bunch({
        'cloudformation': cloudformation,
        'results': results
    })


def do_create(tag, channel, commit, gen_arguments):
    # Generate the single-master and multi-master templates.
    gen_options = gen.get_options_object()
    gen_arguments['master_discovery'] = 'cloud_dynamic'
    single_args = deepcopy(gen_arguments)
    multi_args = deepcopy(gen_arguments)
    single_args['num_masters'] = 1
    multi_args['num_masters'] = 3
    single_master = gen_templates(single_args, gen_options)
    multi_master = gen_templates(multi_args, gen_options)
    button_page = gen_buttons(channel, tag, commit)

    # Make sure we upload the packages for both the multi-master templates as well
    # as the single-master templates.
    extra_packages = list()
    extra_packages += util.cluster_to_extra_packages(single_master.results.cluster_packages)

    return {
        'extra_packages': extra_packages,
        'files': [
            {
                'known_path': 'azure/single-master.cloudformation.json',
                'stable_path': 'azure/{}.single-master.cloudformation.json'.format(
                    single_master.results.arguments['config_id']),
                'content': single_master.cloudformation
            }
        ]
    }
