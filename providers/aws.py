#!/usr/bin/env python3
"""AWS Image Creation, Management, Testing"""

import argparse
import json
import re
import sys
from copy import deepcopy

import jinja2
import requests
import yaml
from pkg_resources import resource_string

import gen
import providers.util as util
from providers.aws_config import session_dev


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
    EnvironmentFile=/opt/mesosphere/environment
    EnvironmentFile=/opt/mesosphere/etc/cfn_signal_metadata
    Environment="AWS_CFN_SIGNAL_THIS_RESOURCE={{ report_name }}"
    ExecStartPre=/bin/ping -c1 leader.mesos
    ExecStartPre=/opt/mesosphere/bin/cfn-signal
    ExecStart=/usr/bin/touch /var/lib/dcos-cfn-signal"""

cf_instance_groups = {
    'master': {
        'report_name': 'MasterServerGroup',
        'roles': ['master', 'aws_master']
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

groups = {
    'master': (
        'master', {
            'report_name': 'MasterServerGroup',
            's3_bucket': '{ "Ref" : "ExhibitorS3Bucket" }',
            's3_prefix': '{ "Ref" : "AWS::StackName" }',
            'exhibitor_storage_backend': 'aws_s3',
            'master_role': '{ "Ref" : "MasterRole" }',
            'agent_role': '',
            'exhibitor_address': '{ "Fn::GetAtt" : [ "InternalMasterLoadBalancer", "DNSName" ] }',
        }),
    'pub-agent': (
        'slave_public', {
            'report_name': 'PublicAgentServerGroup',
            'master_role': '',
            'agent_role': '{ "Ref" : "PublicAgentRole" }',
            'exhibitor_storage_backend': 'agent_only_group_no_exhibitor',
            'exhibitor_address': '{ "Ref" : "InternalMasterLoadBalancerDnsName" }',
        }),
    'priv-agent': (
        'slave', {
            'report_name': 'PrivateAgentServerGroup',
            'master_role': '',
            'agent_role': '{ "Ref" : "PrivateAgentRole" }',
            'exhibitor_storage_backend': 'agent_only_group_no_exhibitor',
            'exhibitor_address': '{ "Ref" : "InternalMasterLoadBalancerDnsName" }',
        })
}

AWS_REF_REGEX = re.compile(r"(?P<before>.*)(?P<ref>{ .* })(?P<after>.*)")


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


def render_cloudformation(cf_template, **kwds):
    # TODO(cmaloney): There has to be a cleaner way to do this transformation.
    # For now just moved from cloud_config_cf.py
    # TODO(cmaloney): Move with the logic that does this same thing in Azure
    def transform_lines(text):
        return ''.join(map(transform, text.splitlines())).rstrip(',\n')

    template_str = gen.template.parse_str(cf_template).render(
        {k: transform_lines(v) for k, v in kwds.items()}
    )

    template_json = json.loads(template_str)

    template_json['Metadata']['DcosImageCommit'] = util.dcos_image_commit
    template_json['Metadata']['TemplateGenerationDate'] = util.template_generation_date

    return json.dumps(template_json)


def gen_supporting_template():
    for template_key in ['infra.json']:
        cf_template = 'aws/templates/advanced/{}'.format(template_key)
        cloudformation = render_cloudformation(resource_string("gen", cf_template).decode())

        print("Validating CloudFormation: {}".format(cf_template))
        client = session_dev.client('cloudformation')
        client.validate_template(TemplateBody=cloudformation)

        yield template_key, gen.Bunch({
            'cloudformation': cloudformation,
            'results': '',
        })


def make_advanced_bunch(variant_args, template_key, template_name, cc_params):
    results = gen.generate(
        mixins=['aws', 'coreos', 'coreos-aws'],
        extra_templates={template_key: [template_name]},
        arguments=variant_args,
        cc_package_files=[
            '/etc/cfn_signal_metadata',
            '/etc/dns_config',
            '/etc/exhibitor',
            '/etc/mesos-master-provider'])

    cloud_config = results.templates['cloud-config']

    # Add general services
    cloud_config = results.utils.add_services(cloud_config)

    cc_variant = deepcopy(cloud_config)
    cc_variant = results.utils.add_units(
        cc_variant,
        yaml.load(gen.template.parse_str(late_services).render(cc_params)))

    # Add roles
    cc_variant = results.utils.add_roles(cc_variant, cc_params['roles'] + ['aws'])

    # NOTE: If this gets printed in string stylerather than '|' the AWS
    # parameters which need to be split out for the cloudformation to
    # interpret end up all escaped and undoing it would be hard.
    variant_cloudconfig = results.utils.render_cloudconfig(cc_variant)

    # Render the cloudformation
    cloudformation = render_cloudformation(
        results.templates[template_key],
        cloud_config=variant_cloudconfig,
        )

    print("Validating CloudFormation: {}".format(template_name))
    client = session_dev.client('cloudformation')
    client.validate_template(TemplateBody=cloudformation)

    return gen.Bunch({
        'cloudformation': cloudformation,
        'results': results
    })


def gen_advanced_template(arguments):
    for variant in ['master', 'priv-agent', 'pub-agent']:
        print('Building advanced template for {}'.format(variant))
        xlated_variant, variant_args = groups[variant]
        variant_args = deepcopy(variant_args)
        variant_args['num_masters'] = "1"
        variant_args.update(arguments)
        params = cf_instance_groups[xlated_variant]
        params['report_name'] = variant_args.pop('report_name')
        template_key = 'advanced-{}'.format(variant)
        template_name = template_key + '.json'
        template_path = 'aws/templates/advanced/' + template_name
        if variant == 'master':
            for num_masters in [1, 3, 5, 7]:
                master_tk = '{}-{}'.format(template_key, num_masters)
                print('Building {} for num_masters = {}'.format(variant, num_masters))
                variant_args['num_masters'] = str(num_masters)
                bunch = make_advanced_bunch(variant_args,
                                            master_tk,
                                            template_path,
                                            params)
                yield '{}.json'.format(master_tk), bunch
        else:
            bunch = make_advanced_bunch(variant_args,
                                        template_key,
                                        template_path,
                                        params)
            yield template_name, bunch


def gen_templates(arguments):
    results = gen.generate(
        mixins=['aws', 'coreos', 'coreos-aws'],
        extra_templates={'cloudformation': ['aws/templates/cloudformation.json']},
        arguments=arguments,
        cc_package_files=[
            '/etc/cfn_signal_metadata',
            '/etc/dns_config',
            '/etc/exhibitor',
            '/etc/mesos-master-provider'])

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
            yaml.load(gen.template.parse_str(late_services).render(params)))

        # Add roles
        cc_variant = results.utils.add_roles(cc_variant, params['roles'] + ['aws'])

        # NOTE: If this gets printed in string stylerather than '|' the AWS
        # parameters which need to be split out for the cloudformation to
        # interpret end up all escaped and undoing it would be hard.
        variant_cloudconfig[variant] = results.utils.render_cloudconfig(cc_variant)

    # Render the cloudformation
    cloudformation = render_cloudformation(
        results.templates['cloudformation'],
        master_cloud_config=variant_cloudconfig['master'],
        slave_cloud_config=variant_cloudconfig['slave'],
        slave_public_cloud_config=variant_cloudconfig['slave_public']
        )

    print("Validating CloudFormation")
    client = session_dev.client('cloudformation')
    client.validate_template(TemplateBody=cloudformation)

    return gen.Bunch({
        'cloudformation': cloudformation,
        'results': results
    })


def gen_buttons(repo_channel_path, channel_commit_path, tag, commit):
    # Generate the button page.
    # TODO(cmaloney): Switch to package_resources
    return env.get_template('aws/templates/aws.html').render(
        {
            'channel_commit_path': channel_commit_path,
            'repo_channel_path': repo_channel_path,
            'tag': tag,
            'commit': commit,
            'regions': aws_region_names
        })


def get_spot_args(base_args):
    spot_args = deepcopy(base_args)
    spot_args['slave_spot_price'] = "0.26"
    spot_args['slave_public_spot_price'] = "0.26"
    return spot_args


def do_create(tag, repo_channel_path, channel_commit_path, commit, variant_arguments):
    # Generate the single-master and multi-master templates.

    extra_packages = list()
    artifacts = list()

    for bootstrap_variant, args in variant_arguments.items():
        # Setup base arguments
        args = deepcopy(args)
        args['exhibitor_address'] = '{ "Fn::GetAtt" : [ "InternalMasterLoadBalancer", "DNSName" ] }'
        args['s3_bucket'] = '{ "Ref" : "ExhibitorS3Bucket" }'
        args['s3_prefix'] = '{ "Ref" : "AWS::StackName" }'
        args['exhibitor_storage_backend'] = 'aws_s3'
        args['master_role'] = '{ "Ref" : "MasterRole" }'
        args['agent_role'] = '{ "Ref" : "SlaveRole" }'

        variant_prefix = util.variant_prefix(bootstrap_variant)

        def add(gen_args, filename):
            nonlocal extra_packages
            gen_out = gen_templates(gen_args)
            artifacts.append({
                'channel_path': 'cloudformation/{}{}'.format(variant_prefix, filename),
                'local_content': gen_out.cloudformation,
                'content_type': 'application/json; charset=utf-8'
                })
            extra_packages += util.cluster_to_extra_packages(gen_out.results.cluster_packages)

        # Single master templates
        single_args = deepcopy(args)
        single_args['num_masters'] = "1"
        add(single_args, 'single-master.cloudformation.json')
        add(get_spot_args(single_args), 'single-master-spot.cloudformation.json')

        # Multi master templates
        multi_args = deepcopy(args)
        multi_args['num_masters'] = "3"
        add(multi_args, 'multi-master.cloudformation.json')
        add(get_spot_args(multi_args), 'multi-master-spot.cloudformation.json')

    # Button page linking to the basic templates.
    button_page = gen_buttons(repo_channel_path, channel_commit_path, tag, commit)
    artifacts.append({
        'channel_path': 'aws.html',
        'local_content': button_page,
        'content_type': 'text/html; charset=utf-8'})

    for template_name, advanced_template in gen_advanced_template(variant_arguments[None]):
        artifacts.append({
            'channel_path': 'cloudformation/{}'.format(template_name),
            'local_content': advanced_template.cloudformation,
            'content_type': 'application/json; charset=utf-8',
        })
        extra_packages += util.cluster_to_extra_packages(advanced_template.results.cluster_packages)

    for template_name, advanced_template in gen_supporting_template():
        artifacts.append({
            'channel_path': 'cloudformation/{}'.format(template_name),
            'local_content': advanced_template.cloudformation,
            'content_type': 'application/json; charset=utf-8',
        })

    return {
        'packages': extra_packages,
        'artifacts': artifacts
    }


def do_print_nat_amis(options):
    region_to_ami = {}

    for region in aws_region_names:
        ec2 = session_dev.client('ec2', region_name=region['id'])

        instances = ec2.describe_images(
            Filters=[{'Name': 'name', 'Values': ['amzn-ami-vpc-nat-hvm-2014.03.2.x86_64-ebs']}])['Images']

        # Sanity check, if it fails spuriously can delete. Just would be odd to
        # get more than one amazon vpc nat AMI.
        assert len(instances) == 1

        region_to_ami[region['id']] = {'default': instances[0]['ImageId']}

    print(json.dumps(region_to_ami, indent=2, sort_keys=True, separators=(', ', ': ')))


def do_print_coreos_amis(options):
    all_amis = requests.get('http://stable.release.core-os.net/amd64-usr/current/coreos_production_ami_all.json').json()
    region_to_ami = {}

    for ami in all_amis['amis']:
        region_to_ami[ami['name']] = {
            'stable': ami['hvm']
        }

    print(json.dumps(region_to_ami, indent=2, sort_keys=True, separators=(', ', ': ')))
    # TODO(cmaloney): Really want to just update hte cloudformation tempalte
    # here, but it isn't real JSON so that is hard.


def main():
    parser = argparse.ArgumentParser(description='AWS DCOS image+template creation, management utilities.')
    subparsers = parser.add_subparsers(title='commands')

    # print_coreos_amis subcommand.
    print_coreos_amis = subparsers.add_parser('print-coreos-amis')
    print_coreos_amis.set_defaults(func=do_print_coreos_amis)

    # print_nat_amis subcommand.
    print_nat_amis = subparsers.add_parser('print-nat-amis')
    print_nat_amis.set_defaults(func=do_print_nat_amis)

    # Parse the arguments and dispatch.
    options = parser.parse_args()

    # Use an if rather than try/except since lots of things inside could throw
    # an AttributeError.
    if hasattr(options, 'func'):
        options.func(options)
        sys.exit(0)
    else:
        parser.print_help()
        print("ERROR: Must use a subcommand")
        sys.exit(1)


if __name__ == '__main__':
    main()
