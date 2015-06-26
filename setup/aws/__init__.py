import boto3
import json
import os
import re
import yaml

from copy import copy, deepcopy
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from subprocess import check_output

aws_region_names = [
    {
        'name': 'US West (N. California)',
        'id': 'us-west-1'
    },
    {
        'name': 'US West (Oregon)',
        'id': 'us-west-2'
    },
    {
        'name': 'US East (N. Virginia)',
        'id': 'us-east-1'
    },
    {
        'name': 'South America (Sao Paulo)',
        'id': 'sa-east-1'
    },
    {
        'name': 'EU (Ireland)',
        'id': 'eu-west-1'
    },
    {
        'name': 'EU (Frankfurt)',
        'id': 'eu-central-1'
    },
    {
        'name': 'Asia Pacific (Tokyo)',
        'id': 'ap-northeast-1'
    },
    {
        'name': 'Asia Pacific (Singapore)',
        'id': 'ap-southeast-1'
    },
    {
        'name': 'Asia Pacific (Sydney)',
        'id': 'ap-southeast-2'
    }]


# TODO(cmaloney): Make a generic parameter to all templates
dcos_image_commit = os.getenv(
    'DCOS_IMAGE_COMMIT',
    os.getenv(
        'BUILD_VCS_NUMBER_ClosedSource_Dcos_ImageBuilder_MesosphereDcosImage2',
        None
        )
    )

if dcos_image_commit is None:
    dcos_image_commit = check_output(['git', 'rev-parse', 'HEAD']).decode('utf-8').strip()

if dcos_image_commit is None:
    raise "Unable to set dcos_image_commit from teamcity or git."

template_generation_date = str(datetime.utcnow())


def load_json(filename):
    try:
        with open(filename) as f:
            return json.load(f)
    except ValueError as ex:
        raise ValueError("Invalid JSON in {0}: {1}".format(filename, ex)) from ex


AWS_REF_REGEX = re.compile(r"(?P<before>.*)(?P<ref>{ .* })(?P<after>.*)")

start_param_simple = '{ "Fn::FindInMap" : [ "Parameters", "'
end_param_simple = '", "default" ] }'
start_param_full = '{ "Ref" : "'
end_param_full = '" }'

# NOTE: Strict undefined behavior since we're doing generation / validation here.
env = Environment(loader=FileSystemLoader('aws/templates'), undefined=StrictUndefined)
launch_template = env.get_template('launch_buttons.md')
params = load_json("aws/cf_param_info.json")
cloudformation_template = env.get_template("cloudformation.json")


def transform(line):
    m = AWS_REF_REGEX.search(line)
    # no splitting necessary
    if not m:
        return "%s,\n" % (json.dumps(line + '\n'))

    before = m.group('before')
    ref = m.group('ref')
    after = m.group('after')

    transformed_before = "%s" % (json.dumps(before))
    transformed_ref = ref
    transformed_after = "%s" % (json.dumps(after))
    return "%s, %s, %s, %s,\n" % (transformed_before, transformed_ref, transformed_after, '"\\n"')


def render_cloudformation(
        simple,
        num_masters,
        master_cloudconfig,
        slave_cloudconfig,
        public_slave_cloudconfig):
    # TODO(cmaloney): There has to be a cleaner way to do this transformation.
    # For now just moved from cloud_config_cf.py
    # TODO(cmaloney): Move with the logic that does this same thing in Azure
    def transform_lines(text):
        return ''.join(map(transform, text.splitlines())).rstrip(',\n')

    template_str = cloudformation_template.render({
        'num_masters': num_masters,
        'master_cloud_config': transform_lines(master_cloudconfig),
        'slave_cloud_config': transform_lines(slave_cloudconfig),
        'public_slave_cloud_config': transform_lines(public_slave_cloudconfig),
        'start_param': start_param_simple if simple else start_param_full,
        'end_param': end_param_simple if simple else end_param_full
    })

    template_json = json.loads(template_str)

    template_json['Metadata']['DcosImageCommit'] = dcos_image_commit
    template_json['Metadata']['TemplateGenerationDate'] = template_generation_date

    local_params = copy(params)

    for param, info in local_params.items():
        if simple:
            if 'Parameters' not in template_json['Mappings']:
                template_json['Mappings']['Parameters'] = {}
            template_json['Mappings']['Parameters'][param] = {'default': info['Default']}
        else:
            template_json['Parameters'][param] = info

    return json.dumps(template_json)


def render_buttons(name):
    return launch_template.render({
        'regions': aws_region_names,
        'name': name
        })

cf_instance_groups = {
    'master': {
        'report_name': 'MasterServerGroup',
        'roles': ['master']
    },
    'slave': {
        'report_name': 'SlaveServerGroup',
        'roles': ['slave']
    },
    'public_slave': {
        'report_name': 'PublicSlaveServerGroup',
        'roles': ['public_slave']
    }
}

late_services = """- name: cfn-signal.service
  command: start
  content: |
    [Unit]
    Description=Signal CloudFormation Success
    After=dcos.target
    Requires=dcos.target
    ConditionPathExists=!/var/lib/cfn-signal
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
    ExecStart=/usr/bin/touch /var/lib/cfn-signal"""

# TODO(cmaloney): Make it so we can load extra parameters from jina templates
# per-provider.
# TODO(cmaloney): Should provide a hook for various providers to give a argument
# calculator to go with their extra templates (and the templates in general).

provider_templates = ['templates/cloudformation.json']


def gen(cloud_config, arguments, utils):
    # Add general services
    cloud_config = utils.add_services(cloud_config)

    # Specialize for master, slave, public_slave
    variant_cloudconfig = {}
    for variant, params in cf_instance_groups.items():
        cc_variant = deepcopy(cloud_config)

        # Specialize the cfn-signal service
        cc_variant = utils.add_units(
            cc_variant,
            yaml.load(env.from_string(late_services).render(params)))

        # Add roles
        cc_variant = utils.add_roles(cc_variant, params['roles'] + ['aws'])

        # NOTE: If this gets printed in string stylerather than '|' the AWS
        # parameters which need to be split out for the cloudformation to
        # interpret end up all escaped and undoing it would be hard.
        variant_cloudconfig[variant] = utils.render_cloudconfig(cc_variant)

    # Render the cloudformation
    cloudformation = render_cloudformation(
        True,
        arguments['num_masters'],
        variant_cloudconfig['master'],
        variant_cloudconfig['slave'],
        variant_cloudconfig['public_slave']
        )

    # Write it out
    with open('cloudformation.json', 'w') as f:
        f.write(cloudformation)

    print("Validating CloudFormation")
    client = boto3.client('cloudformation')
    client.validate_template(TemplateBody=cloudformation)
