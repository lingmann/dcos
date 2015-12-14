#!/usr/bin/env python3
"""Azure Image Creation, Management, Testing"""

import json
import re
import sys
import urllib
from copy import deepcopy

import yaml

import gen
import gen.template
import providers.util as util

# TODO(cmaloney): Make it so the template only completes when services are properly up.
late_services = ""

ILLEGAL_ARM_CHARS_PATTERN = re.compile("[']")

TEMPLATE_PATTERN = re.compile('(?P<pre>.*?)\[\[\[(?P<inject>.*?)\]\]\]')

UPLOAD_URL = ("http://az837203.vo.msecnd.net/dcos/{channel}"
              "/azure/azure/{config_id}.single-master.azuredeploy.json")

INSTANCE_GROUPS = {
    'master': {
        'report_name': 'MasterServerGroup',
        'roles': ['master', 'azure_master']
    },
    'slave': {
        'report_name': 'SlaveServerGroup',
        'roles': ['slave']
    },
    'slave_public': {
        'report_name': 'PublicSlaveServerGroup',
        'roles': ['slave_public']
    }
}


def validate_cloud_config(cc_string):
    '''
    Validate that there aren't any single quotes present since they break the
    ARM template system. Exit with an error message if any invalid characters
    are detected.

    @param cc_string: str, Cloud Configuration
    '''
    illegal_match = ILLEGAL_ARM_CHARS_PATTERN.search(cc_string)
    if illegal_match:
        print("ERROR: Illegal cloud config string detected.", file=sys.stderr)
        print("ERROR: {} matches pattern {}".format(
            illegal_match.string, illegal_match.re), file=sys.stderr)
        sys.exit(1)


def transform(cloud_config_yaml_str):
    '''
    Transforms the given yaml into a list of strings which are concatenated
    together by the ARM template system. We must make it a list of strings so
    that ARM template parameters appear at the top level of the template and get
    substituted.
    '''
    cc_json = json.dumps(yaml.load(cloud_config_yaml_str), sort_keys=True)
    arm_list = ["[base64(concat('#cloud-config\n\n', "]
    # Find template parameters and seperate them out as seperate elements in a
    # json list.
    prev_end = 0
    # TODO(JL) - Why does validate_cloud_config not operate on entire string?
    for m in TEMPLATE_PATTERN.finditer(cc_json):
        before = m.group('pre')
        param = m.group('inject')
        validate_cloud_config(before)
        arm_list.append("'{}', {},".format(before, param))
        prev_end = m.end()

    # Add the last little bit
    validate_cloud_config(cc_json[prev_end:])
    arm_list.append("'{}'))]".format(cc_json[prev_end:]))

    # We're embedding this as a json string, so json encode it and return.
    return json.dumps(''.join(arm_list))


def render_arm(
        master_cloudconfig_yaml_str,
        slave_cloudconfig_yaml_str,
        slave_public_cloudconfig_yaml_str):

    template_str = gen.template.parse_resources('azure/azuredeploy.json').render({
        'master_cloud_config': transform(master_cloudconfig_yaml_str),
        'slave_cloud_config': transform(slave_cloudconfig_yaml_str),
        'slave_public_cloud_config': transform(slave_public_cloudconfig_yaml_str)
    })

    # Add in some metadata to help support engineers
    template_json = json.loads(template_str)
    template_json['variables']['DcosImageCommit'] = util.dcos_image_commit
    template_json['variables']['TemplateGenerationDate'] = util.template_generation_date
    return json.dumps(template_json)


def gen_templates(user_args, options):
    '''
    Render the cloud_config template given a particular set of options

    @param user_args: dict, args to pass to the gen library. These are user
                     input arguments which get filled in/prompted for.
    @param options: Options to control the gen library itself, such as whether
                     to save the user config, the final generated config, if it
                     is non-interactive
    '''
    results = gen.generate(
        options=options,
        # Mixins which add mounting the drive, disabling etcd, provider config
        # around how to access the master load balancer, etc.
        mixins=['azure', 'coreos'],
        # jinja template
        arguments=user_args,
        cc_package_files=[
            '/etc/dns_config',
            '/etc/exhibitor',
            '/etc/exhibitor.properties',
            '/etc/mesos-master-provider']
        )

    # Add general services
    cloud_config = results.utils.add_services(results.templates['cloud-config'])

    # Specialize for master, slave, slave_public
    variant_cloudconfig = {}
    for variant, params in INSTANCE_GROUPS.items():
        cc_variant = deepcopy(cloud_config)

        # TODO(cmaloney): Add the dcos-arm-signal service here
        # cc_variant = results.utils.add_units(
        #     cc_variant,
        #     yaml.load(gen.template.parse_str(late_services).render(params)))

        # Add roles
        cc_variant = results.utils.add_roles(cc_variant, params['roles'] + ['azure'])

        # NOTE: If this gets printed in string stylerather than '|' the Azure
        # parameters which need to be split out for the arm to
        # interpret end up all escaped and undoing it would be hard.
        variant_cloudconfig[variant] = results.utils.render_cloudconfig(cc_variant)

    # Render the arm
    arm = render_arm(
        variant_cloudconfig['master'],
        variant_cloudconfig['slave'],
        variant_cloudconfig['slave_public']
        )

    return gen.Bunch({
        'arm': arm,
        'results': results
    })


def do_create(tag, channel, commit, gen_arguments):
    # Generate the single-master and multi-master templates.
    gen_options = gen.get_options_object()
    gen_arguments['master_discovery'] = 'cloud_dynamic'
    single_args = deepcopy(gen_arguments)
    single_args['num_masters'] = '1'
    single_master = gen_templates(single_args, gen_options)
    single_master_config_id = single_master.results.arguments['config_id']

    # Make sure we upload the packages for both the multi-master templates as
    # well as the single-master templates.
    extra_packages = util.cluster_to_extra_packages(single_master.results.cluster_packages)

    return {
        'extra_packages': extra_packages,
        'files': [
            {
                'known_path': 'azure/single-master.azuredeploy.json',
                'stable_path': 'azure/{}.single-master.azuredeploy.json'.format(single_master_config_id),
                'content': single_master.arm
            },
            {
                'known_path': 'azure.html',
                'content': gen_buttons(channel, tag, commit, single_master_config_id),
                'upload_args': {
                    'ContentType': 'text/html; charset=utf-8'
                }
            }
        ]
    }


def gen_buttons(channel, tag, commit, single_master_config_id):
    '''
    Generate the button page, that is, "Deploy a cluster to Azure" page
    '''
    template_upload_url = UPLOAD_URL.format(channel=channel, config_id=single_master_config_id)
    return gen.template.parse_resources('azure/templates/azure.html').render({
        'channel': channel,
        'tag': tag,
        'commit': commit,
        'template_url': encode_url_as_param(template_upload_url)
    })


# Escape URL characters like '/' and ':' so that it can be used with the Azure
# web endpoint of https://portal.azure.com/#create/Microsoft.Template/uri/
def encode_url_as_param(s):
    s = s.encode('utf8')
    s = urllib.parse.quote_plus(s)
    return s
