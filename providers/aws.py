#!/usr/bin/env python3
"""AWS Image Creation, Management, Testing"""

import argparse
import json
import re
import sys
from copy import deepcopy

import botocore.exceptions
import requests
import yaml

import gen
import providers.util as util
from providers.aws_config import session_dev, session_prod

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
    EnvironmentFile=/opt/mesosphere/etc/cloudenv
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


def render_cloudformation(
        cf_template,
        master_cloudconfig,
        slave_cloudconfig,
        slave_public_cloudconfig):
    # TODO(cmaloney): There has to be a cleaner way to do this transformation.
    # For now just moved from cloud_config_cf.py
    # TODO(cmaloney): Move with the logic that does this same thing in Azure
    def transform_lines(text):
        return ''.join(map(transform, text.splitlines())).rstrip(',\n')

    template_str = gen.env.from_string(cf_template).render(
        {
            'master_cloud_config': transform_lines(master_cloudconfig),
            'slave_cloud_config': transform_lines(slave_cloudconfig),
            'slave_public_cloud_config': transform_lines(slave_public_cloudconfig)
        })

    template_json = json.loads(template_str)

    template_json['Metadata']['DcosImageCommit'] = util.dcos_image_commit
    template_json['Metadata']['TemplateGenerationDate'] = util.template_generation_date

    return json.dumps(template_json)


def gen_templates(arguments, options):
    results = gen.generate(
        options=options,
        mixins=['aws', 'coreos', 'coreos-aws'],
        extra_templates={'cloudformation': ['aws/templates/cloudformation.json']},
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
            yaml.load(gen.env.from_string(late_services).render(params)))

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
        variant_cloudconfig['slave'],
        variant_cloudconfig['slave_public']
        )

    print("Validating CloudFormation")
    client = session_prod.client('cloudformation')
    client.validate_template(TemplateBody=cloudformation)

    return gen.Bunch({
        'cloudformation': cloudformation,
        'results': results
    })


def gen_buttons(channel, tag, commit):
    # Generate the button page.
    # TODO(cmaloney): Switch to package_resources
    return gen.env.get_template('aws/templates/aws.html').render(
        {
            'channel': channel,
            'tag': tag,
            'commit': commit,
            'regions': aws_region_names
        })


def get_spot_args(base_args):
    spot_args = deepcopy(base_args)
    spot_args['slave_spot_price'] = "0.26"
    spot_args['slave_public_spot_price'] = "0.26"
    return spot_args


def do_create(tag, channel, commit, gen_arguments):
    # Generate the single-master and multi-master templates.
    gen_options = gen.get_options_object()
    gen_arguments['master_discovery'] = 'cloud_dynamic'
    single_args = deepcopy(gen_arguments)
    multi_args = deepcopy(gen_arguments)
    single_args['num_masters'] = "1"
    multi_args['num_masters'] = "3"
    single_master = gen_templates(single_args, gen_options)
    multi_master = gen_templates(multi_args, gen_options)
    single_master_spot = gen_templates(get_spot_args(single_args), gen_options)
    multi_master_spot = gen_templates(get_spot_args(single_args), gen_options)
    button_page = gen_buttons(channel, tag, commit)

    # Make sure we upload the packages for both the multi-master templates as well
    # as the single-master templates.
    extra_packages = list()
    extra_packages += util.cluster_to_extra_packages(multi_master.results.cluster_packages)
    extra_packages += util.cluster_to_extra_packages(single_master.results.cluster_packages)
    extra_packages += util.cluster_to_extra_packages(multi_master_spot.results.cluster_packages)
    extra_packages += util.cluster_to_extra_packages(single_master_spot.results.cluster_packages)

    return {
        'extra_packages': extra_packages,
        'files': [
            {
                'known_path': 'cloudformation/single-master.cloudformation.json',
                'stable_path': 'cloudformation/{}.single-master.cloudformation.json'.format(
                    single_master.results.arguments['config_id']),
                'content': single_master.cloudformation
            },
            {
                'known_path': 'cloudformation/multi-master.cloudformation.json',
                'stable_path': 'cloudformation/{}.multi-master.cloudformation.json'.format(
                    multi_master.results.arguments['config_id']),
                'content': multi_master.cloudformation
            },
            {
                'known_path': 'cloudformation/single-master-spot.cloudformation.json',
                'stable_path': 'cloudformation/{}.single-master-spot.cloudformation.json'.format(
                    single_master_spot.results.arguments['config_id']),
                'content': single_master_spot.cloudformation
            },
            {
                'known_path': 'cloudformation/multi-master-spot.cloudformation.json',
                'stable_path': 'cloudformation/{}.multi-master-spot.cloudformation.json'.format(
                    multi_master_spot.results.arguments['config_id']),
                'content': multi_master_spot.cloudformation
            },
            {
                'known_path': 'aws.html',
                'content': button_page,
                'upload_args': {
                    'ContentType': 'text/html; charset=utf-8'
                }
            }
        ]
    }


def do_print_nat_amis(options):
    region_to_ami = {}

    for region in aws_region_names:
        ec2 = session_prod.client('ec2', region_name=region['id'])

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


def delete_s3_nonempty(bucket):
    # This is an exhibitor bucket, should only have one item in it. Die hard rather
    # than accidentally doing the wrong thing if there is more.

    objects = [bucket.objects.all()]
    assert len(objects) == 1

    # While almost everything s3 is region agnostic (Including the listing,
    # uploading, etc), for deleting things the Hamburg region has different
    # auth than other regions, and if you use an s3 client from the wrong region
    # things break. So figure out the bucket's region, make a s3 resource for
    # that region, then delete that way.
    s3_client = session_dev.client('s3')
    region = s3_client.get_bucket_location(Bucket=bucket.name)['LocationConstraint']

    region_s3 = session_dev.resource('s3', region_name=region)

    region_bucket = region_s3.Bucket(bucket.name)

    for obj in region_bucket.objects.all():
        obj.delete()

    region_bucket.delete()


def delete_stack(stack):
    # Delete the s3 bucket
    stack_resource = stack.Resource('ExhibitorS3Bucket')
    try:
        bucket = session_dev.resource('s3').Bucket(stack_resource.physical_resource_id)
        delete_s3_nonempty(bucket)
    except botocore.exceptions.ClientError as ex:
        print("ERROR deleting bucket:", ex)

    # Delete the stack
    stack.delete()


def do_clean_stacks(options):
    # Cycle through regions, listing all cloudformation stacks and prompting for
    # each if it should be deleted. If yes, delete the stack and s3 bucket
    for region in [region['id'] for region in aws_region_names]:
        client = session_dev.resource('cloudformation', region_name=region)

        # Do a for to convert from iterator to list
        stacks = [stack for stack in client.stacks.all()]

        for stack in stacks:
            print("Stack: {}".format(stack.stack_name))
            print("Launched: {}".format(stack.creation_time))
            # Loop until y or n is given
            while True:
                delete = input("Delete? [y/n]: ")
                if delete == 'y':
                    delete_stack(stack)
                    break
                elif delete == 'n':
                    break


def do_clean_buckets(options):
    # List s3 buckets, Prompt to delete any that don't have an associated stack
    s3 = session_dev.resource('s3')
    buckets = [bucket for bucket in s3.buckets.all()]

    # NOTE: We list s3 buckets before cf stacks so that we hopefully don't get
    # any stacks just starting up.

    # Get all the current cf stack buckets
    cf_buckets = []
    for region in [region['id'] for region in aws_region_names]:
        cf = session_dev.resource('cloudformation', region_name=region)

        for stack in cf.stacks.all():
            for resource in stack.resource_summaries.all():
                if resource.logical_resource_id == 'ExhibitorS3Bucket':
                    if resource.physical_resource_id is None:
                        break
                    cf_buckets.append(resource.physical_resource_id)
                    break

    for bucket in buckets:
        if bucket.name in cf_buckets:
            continue

        # TODO(cmaloney): This should be a 'prompt' function.
        while True:
            delete = input("{} [y/n]: ".format(bucket.name))
            if delete == 'y':
                try:
                    delete_s3_nonempty(bucket)
                except Exception as ex:
                    print("ERROR", ex)
                    print("ERROR: Unable to delete", bucket.name)
                break
            elif delete == 'n':
                break


def main():
    parser = argparse.ArgumentParser(description='AWS DCOS image+template creation, management utilities.')
    subparsers = parser.add_subparsers(title='commands')

    # print_coreos_amis subcommand.
    print_coreos_amis = subparsers.add_parser('print-coreos-amis')
    print_coreos_amis.set_defaults(func=do_print_coreos_amis)

    # print_nat_amis subcommand.
    print_nat_amis = subparsers.add_parser('print-nat-amis')
    print_nat_amis.set_defaults(func=do_print_nat_amis)

    # cleanup_cf_stacks
    clean_stacks = subparsers.add_parser('clean_stacks')
    clean_stacks.set_defaults(func=do_clean_stacks)

    # cleanup s3 buckets
    clean_stacks = subparsers.add_parser('clean_buckets')
    clean_stacks.set_defaults(func=do_clean_buckets)

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
