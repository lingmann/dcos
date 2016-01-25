#!/usr/bin/env python3
"""Azure Image Creation, Management, Testing"""

import json
import re
import sys
import urllib
from copy import deepcopy

import jinja2
import yaml
from pkg_resources import resource_string

import gen
import gen.template
import providers.util as util


# TODO(cmaloney): Remove this last use of jinja2. It contains a for loop which
# is beyond what we compute currently.
# Function to allow jinja to load our templates folder layout. This uses
# resource_string from pkg_resources which is the recommended way of getting
# files out of a package however it is distributed
# (See: https://pythonhosted.org/setuptools/pkg_resources.html)
# For the jinja function loader documentation, see:
# http://jinja.pocoo.org/docs/dev/api/#jinja2.FunctionLoader
def load_template(name):
    contents = resource_string("gen", name).decode()

    # The templates from our perspective are always invalidated / never cacheable.
    def false_func():
        return False

    return (contents, name, false_func)

# NOTE: Strict undefined behavior since we're doing generation / validation here.
env = jinja2.Environment(
    loader=jinja2.FunctionLoader(load_template),
    undefined=jinja2.StrictUndefined,
    keep_trailing_newline=True)

# TODO(cmaloney): Make it so the template only completes when services are properly up.
late_services = ""

ILLEGAL_ARM_CHARS_PATTERN = re.compile("[']")

TEMPLATE_PATTERN = re.compile('(?P<pre>.*?)\[\[\[(?P<inject>.*?)\]\]\]')

UPLOAD_URL = ("http://az837203.vo.msecnd.net/dcos/{channel_commit_path}/azure/{arm_template_name}")

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
        arm_template,
        master_cloudconfig_yaml_str,
        slave_cloudconfig_yaml_str,
        slave_public_cloudconfig_yaml_str):

    template_str = gen.template.parse_str(arm_template).render({
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
        extra_templates={'azuredeploy': ['azure/templates/azuredeploy.json']},
        arguments=user_args,
        cc_package_files=[
            '/etc/exhibitor',
            '/etc/exhibitor.properties',
            '/etc/mesos-master-provider',
            '/etc/master_list']
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
        results.templates['azuredeploy'],
        variant_cloudconfig['master'],
        variant_cloudconfig['slave'],
        variant_cloudconfig['slave_public']
        )

    return gen.Bunch({
        'arm': arm,
        'results': results
    })


def master_list_arm_json(num_masters):
    '''
    Return a JSON string containing a list of ARM expressions for the master IP's of the cluster.

    @param num_masters: int, number of master nodes in the cluster
    '''
    arm_expression = "[[[reference('masterNodeNic{}').ipConfigurations[0].properties.privateIPAddress]]]"
    return json.dumps([arm_expression.format(x) for x in range(num_masters)])


def do_create(tag, repo_channel_path, channel_commit_path, commit, gen_arguments):
    # Generate the template varietals: 1, 3, and 5 master nodes
    gen_options = gen.get_options_object()

    gen_arguments['master_list'] = master_list_arm_json(1)
    args_1master = deepcopy(gen_arguments)
    gen_arguments['master_list'] = master_list_arm_json(3)
    args_3master = deepcopy(gen_arguments)
    gen_arguments['master_list'] = master_list_arm_json(5)
    args_5master = deepcopy(gen_arguments)

    dcos_1master = gen_templates(args_1master, gen_options)
    dcos_3master = gen_templates(args_3master, gen_options)
    dcos_5master = gen_templates(args_5master, gen_options)

    # Make sure we upload the packages for all template varietals.
    extra_packages = list()
    extra_packages += util.cluster_to_extra_packages(dcos_1master.results.cluster_packages)
    extra_packages += util.cluster_to_extra_packages(dcos_3master.results.cluster_packages)
    extra_packages += util.cluster_to_extra_packages(dcos_5master.results.cluster_packages)

    return {
        'packages': extra_packages,
        'artifacts': [
            {
                'channel_path': 'azure/dcos-1master.azuredeploy.json',
                'local_content': dcos_1master.arm,
                'content_type': 'application/json; charset=utf-8'
            },
            {
                'channel_path': 'azure/dcos-3master.azuredeploy.json',
                'local_content': dcos_3master.arm,
                'content_type': 'application/json; charset=utf-8'
            },
            {
                'channel_path': 'azure/dcos-5master.azuredeploy.json',
                'local_content': dcos_5master.arm,
                'content_type': 'application/json; charset=utf-8'
            },
            {
                'channel_path': 'azure.html',
                'local_content': gen_buttons(repo_channel_path, channel_commit_path, tag, commit),
                'content_type': 'text/html; charset=utf-8'
            }
        ]
    }


def gen_buttons(repo_channel_path, channel_commit_path, tag, commit):
    '''
    Generate the button page, that is, "Deploy a cluster to Azure" page
    '''
    arm_urls = [
        {
            'name': '1 Master',
            'encoded_url': encode_url_as_param(UPLOAD_URL.format(
                channel_commit_path=channel_commit_path,
                arm_template_name='dcos-1master.azuredeploy.json'))
        },
        {
            'name': '3 Masters',
            'encoded_url': encode_url_as_param(UPLOAD_URL.format(
                channel_commit_path=channel_commit_path,
                arm_template_name='dcos-3master.azuredeploy.json'))
        },
        {
            'name': '5 Masters',
            'encoded_url': encode_url_as_param(UPLOAD_URL.format(
                channel_commit_path=channel_commit_path,
                arm_template_name='dcos-5master.azuredeploy.json'))
        }]
    return env.get_template('azure/templates/azure.html').render({
        'repo_channel_path': repo_channel_path,
        'tag': tag,
        'commit': commit,
        'arm_urls': arm_urls
    })


# Escape URL characters like '/' and ':' so that it can be used with the Azure
# web endpoint of https://portal.azure.com/#create/Microsoft.Template/uri/
def encode_url_as_param(s):
    s = s.encode('utf8')
    s = urllib.parse.quote_plus(s)
    return s
