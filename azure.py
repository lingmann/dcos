#!/usr/bin/env python3
"""Azure Image Creation, Management, Testing"""

import json
import re
import sys
import urllib
import yaml

from copy import deepcopy

import gen
import util

from gen.azure.azure_client import AzureClient

# TODO(cmaloney): Make it so the template only completes when services are properly up.
late_services = ""

instance_groups = {
    'master': {
        'report_name': 'MasterServerGroup',
        'roles': ['master', 'azure_master']
    },
    'slave': {
        'report_name': 'SlaveServerGroup',
        'roles': ['slave']
    }
}


# Validate that there aren't any single quotes present since they break the ARM
# template system.
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


# Transforms the given yaml to be a list of strings which are concatenated
# together by the ARM template system. We must make it a list of strings so that
# ARM template parameters appear at the top level of the template and get substituted
def transform(cloud_config_yaml_str):
    cc_json = json.dumps(yaml.load(cloud_config_yaml_str), sort_keys=True)
    arm_list_str = "[base64(concat('#cloud-config\n\n', "
    # Find template parameters and seperate them out as seperate elements in a
    # json list.
    prevend = 0
    for m in re.finditer('(?P<pre>.*?)\[\[\[(?P<inject>.*?)\]\]\]', cc_json):
        before = m.group('pre')
        param = m.group('inject')
        validate_cloud_config(before)
        arm_list_str += "'{}', {},".format(before, param)
        prevend = m.end()

    # Add the last little bit
    validate_cloud_config(cc_json[prevend:])
    arm_list_str += "'{}'))]".format(cc_json[prevend:])

    # We're embedding this as a json string, so json encode it and return.
    return json.dumps(arm_list_str)


def render_arm(
        arm_template_json_str,
        master_cloudconfig_yaml_str,
        slave_cloudconfig_yaml_str):

    template_str = util.jinja_env.from_string(arm_template_json_str).render({
        'master_cloud_config': transform(master_cloudconfig_yaml_str),
        'slave_cloud_config': transform(slave_cloudconfig_yaml_str)
    })

    # Add in some metadata to help support engineers
    template_json = json.loads(template_str)
    template_json['variables']['DcosImageCommit'] = util.dcos_image_commit
    template_json['variables']['TemplateGenerationDate'] = util.template_generation_date
    return json.dumps(template_json)


# Render the cloud_config template given a particular set of options
#
# Arguments:
#   arguments: a python dictionary of arguments to pass to the gen library. They
#     are user input arguments which get filled in / prompted for
#   options: Options to control the gen library itself, such as whether to save
#     the user config, the final generated config, if it is non-interactive
def gen_templates(arguments, options):
    results = gen.generate(
        options=options,
        # Mixins which add mounting the drive, disabling etcd, provider config
        # around how to access the master load balancer, etc.
        mixins=['azure', 'coreos'],
        # jinja template
        arguments=arguments
        )

    cloud_config = results.templates['cloud-config']

    # Add general services
    cloud_config = results.utils.add_services(cloud_config)

    # Specialize for master, slave, slave_public
    variant_cloudconfig = {}
    for variant, params in instance_groups.items():
        cc_variant = deepcopy(cloud_config)

        # TODO(cmaloney): Add the dcos-arm-signal service here
        # cc_variant = results.utils.add_units(
        #     cc_variant,
        #     yaml.load(util.jinja_env.from_string(late_services).render(params)))

        # Add roles
        cc_variant = results.utils.add_roles(cc_variant, params['roles'] + ['azure'])

        # NOTE: If this gets printed in string stylerather than '|' the Azure
        # parameters which need to be split out for the arm to
        # interpret end up all escaped and undoing it would be hard.
        variant_cloudconfig[variant] = results.utils.render_cloudconfig(cc_variant)

    # Render the arm
    arm = render_arm(
        open('gen/azure/azuredeploy.json').read(),
        variant_cloudconfig['master'],
        variant_cloudconfig['slave']
        )

    client = AzureClient.createFromEnvCreds()

    template_parameters = {
        "sshKeyData": {"value": "parametervalue1"},
        "authorizedSubnet": {"value": "10.0.0.0"},
        "region": {"value": "West US"},
        "numberOfMasters": {"value": 1},
        "numberOfPrivateSlaves": {"value": 5}
        }

    # Use RPC against azure to validate the ARM template is well-formed
    client.verify(template_body_json=json.loads(arm), template_parameters=template_parameters)
    print("Template OK")

    return gen.Bunch({
        'arm': arm,
        'results': results
    })


def do_create(tag, channel, commit, gen_arguments):
    # Generate the single-master and multi-master templates.
    gen_options = gen.get_options_object()
    gen_arguments['master_discovery'] = 'cloud_dynamic'
    single_args = deepcopy(gen_arguments)
    single_args['num_masters'] = 1
    single_master = gen_templates(single_args, gen_options)
    button_page = gen_buttons(channel, tag, commit)

    # Make sure we upload the packages for both the multi-master templates as
    # well as the single-master templates.
    extra_packages = list()
    extra_packages += util.cluster_to_extra_packages(single_master.results.cluster_packages)

    return {
        'extra_packages': extra_packages,
        'files': [
            {
                'known_path': 'azure/single-master.azuredeploy.json',
                'stable_path': 'azure/{}.single-master.azuredeploy.json'.format(
                    single_master.results.arguments['config_id']),
                'content': single_master.arm
            },
            {
                'known_path': 'azure.html',
                'content': button_page,
                'upload_args': {
                    'ContentType': 'text/html; charset=utf-8'
                }
            }
        ]
    }


def gen_buttons(channel, tag, commit):
    # Generate the button page.
    template_url = "https://s3.amazonaws.com/downloads.mesosphere.io/dcos/{}/azure/single-master.azuredeploy.json".format(channel)
    return util.jinja_env.from_string(open('gen/azure/templates/azure.html').read()).render({
            'channel': channel,
            'tag': tag,
            'commit': commit,
            'template_url': urlencode(template_url)
        })


def urlencode(s):
    s = s.encode('utf8')
    s = urllib.parse.quote_plus(s)
    return s
