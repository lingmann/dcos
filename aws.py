#!/usr/bin/env python3
"""AWS Image Creation, Management, Testing

Usage:
    aws.py build [--upload] [--skip-package-build]
    # promote_candidate <release_name> instead?
    aws.py make_candidate <release_name>
    aws.py promote_candidate <release_name>
    aws.py promote <from_release> <to_release>
    aws.py cluster launch <name> [--cf-url=<url>|--release_name=<release_name>]
    aws.py cluster resume # Reads last test launched stack name out of file.
    aws.py cluster delete <name>
    aws.py print_coreos_amis
    aws.py print_nat_amis
"""
import argparse
import binascii
import boto3
import getpass
import hashlib
import jinja2
import json
import os
import re
import requests
import sys
import time
import uuid
import yaml
from copy import copy, deepcopy
from datetime import datetime
from pkgpanda import PackageId
from pkgpanda.util import load_json, load_string, write_json
from subprocess import check_call, check_output

import gen
# TODO(cmaloney): Move upload_s3 into this.
from util import upload_s3, get_object

base_env = deepcopy(os.environ)

prod_env = deepcopy(os.environ)
prod_env['AWS_PROFILE'] = 'production'

dev_env = deepcopy(os.environ)
dev_env['AWS_PROFILE'] = 'development'

jinja_env = jinja2.Environment(
        undefined=jinja2.StrictUndefined)

params = load_json("gen/aws/cf_param_info.json")

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


def download_s3(obj, out_file):
    body = obj.get()['Body']
    with open(out_file, 'wb') as dest:
        for chunk in iter(lambda: body.read(4096), b''):
            dest.write(chunk)


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
        public_slave_cloudconfig):
    # TODO(cmaloney): There has to be a cleaner way to do this transformation.
    # For now just moved from cloud_config_cf.py
    # TODO(cmaloney): Move with the logic that does this same thing in Azure
    def transform_lines(text):
        return ''.join(map(transform, text.splitlines())).rstrip(',\n')

    print(cf_template)
    template_str = jinja_env.from_string(cf_template).render({
        'master_cloud_config': transform_lines(master_cloudconfig),
        'slave_cloud_config': transform_lines(slave_cloudconfig),
        'public_slave_cloud_config': transform_lines(public_slave_cloudconfig)
    })

    template_json = json.loads(template_str)

    template_json['Metadata']['DcosImageCommit'] = dcos_image_commit
    template_json['Metadata']['TemplateGenerationDate'] = template_generation_date

    local_params = copy(params)

    for param, info in local_params.items():
        if 'Parameters' not in template_json['Mappings']:
            template_json['Mappings']['Parameters'] = {}
        template_json['Mappings']['Parameters'][param] = {'default': info['Default']}
    return json.dumps(template_json)


def upload_cf(release_name, cf_id, text):
    cf_object = get_object(release_name, 'cloudformation/{}.cloudformation.json'.format(cf_id))
    cf_object.put(Body=text.encode('utf-8'), CacheControl='no-cache')

    return 'https://s3.amazonaws.com/downloads.mesosphere.io/{}'.format(cf_object.key)


def upload_packages(release_name, bootstrap_id, config_package_id):
    def upload(*args, **kwargs):
        return upload_s3(release_name, if_not_exists=True, *args, **kwargs)

    # Upload packages
    for id_str in load_json('packages/{}.active.json'.format(bootstrap_id)):
        id = PackageId(id_str)
        upload('packages/{name}/{id}.tar.xz'.format(name=id.name, id=id_str))

    # Upload bootstrap
    upload('packages/{}.bootstrap.tar.xz'.format(bootstrap_id),
           'bootstrap/{}.bootstrap.tar.xz'.format(bootstrap_id))
    upload('packages/{}.active.json'.format(bootstrap_id),
           'config/{}.active.json'.format(bootstrap_id))

    # Upload the config package
    upload('{}.tar.xz'.format(config_package_id),
           'packages/dcos-config--setup/{}.tar.xz'.format(config_package_id))


def build_packages():
    check_call(['mkpanda', 'tree', '--mkbootstrap'], cwd='packages', env=base_env)
    return load_string('packages/bootstrap.latest')


def gen_templates(arguments, options):
    results = gen.generate(
        options=options,
        mixins=['aws', 'coreos', 'coreos-aws'],
        extra_templates={'cloudformation': ['gen/aws/templates/cloudformation.json']},
        arguments=arguments
        )

    cloud_config = results.templates['cloud-config']

    # Add general services
    cloud_config = results.utils.add_services(cloud_config)

    # Specialize for master, fslave, public_slave
    variant_cloudconfig = {}
    for variant, params in cf_instance_groups.items():
        cc_variant = deepcopy(cloud_config)

        # Specialize the cfn-signal service
        cc_variant = results.utils.add_units(
            cc_variant,
            yaml.load(jinja_env.from_string(late_services).render(params)))

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
        variant_cloudconfig['public_slave']
        )

    print("Validating CloudFormation")
    client = boto3.client('cloudformation')
    client.validate_template(TemplateBody=cloudformation)

    return gen.Bunch({
        'cloudformation': cloudformation,
        'results': results
    })


def do_build(options):
    # TODO(cmaloney): don't shell out to mkpanda
    if not options.skip_package_build:
        bootstrap_id = build_packages()
    else:
        bootstrap_id = load_string('packages/bootstrap.latest')

    release_name = 'testing/' + options.testing_name

    templates = gen_templates({'bootstarp_id': bootstrap_id, 'release_name': release_name}, options)

    # TODO(cmaloney): print out the final cloudformation s3 path.
    if options.upload:
        cf_bytes = templates.cloudformation.encode('utf-8')
        hasher = hashlib.sha1()
        hasher.update(cf_bytes)
        cf_id = binascii.hexlify(hasher.digest()).decode('ascii')
        upload_packages(
                release_name,
                bootstrap_id,
                templates.results.arguments['config_package_id'])
        cf_path = upload_cf(release_name, cf_id, templates.cloudformation)
        print("CloudFormation to launch: ", cf_path)


def gen_buttons(release_name, title):
    # Generate the button page.
    return jinja_env.from_string(open('gen/aws/templates/aws.html').read()).render({
        'regions': aws_region_names,
        'release_name': release_name,
        'title': title
        })


def upload_buttons(release_name, content):
    get_object(release_name, 'aws.html').put(
            Body=content.encode('utf-8'),
            CacheControl='no-cache',
            ContentType='text/html')


def do_make_candidate(options):
    # Make sure everything is built / up to date.
    bootstrap_id = build_packages()
    release_name = 'testing/' + options.release_name

    # Generate the single-master and multi-master templates.
    options = gen.get_options_object()
    single_master = gen_templates(
            {'bootstrap_id': bootstrap_id, 'release_name': release_name, 'num_masters': 1},
            options)
    multi_master = gen_templates(
            {'bootstrap_id': bootstrap_id, 'release_name': release_name, 'num_masters': 3},
            options)

    button_page = gen_buttons(release_name, "RC for " + options.release_name)

    # Upload the packages.
    upload_packages(
            release_name,
            bootstrap_id,
            single_master.results.arguments['config_package_id'])
    upload_cf(release_name, 'single-master', single_master.cloudformation)
    upload_cf(release_name, 'multi-master', multi_master.cloudformation)

    # Upload button page
    upload_buttons(release_name, button_page)

    print("Candidate availabel at: https://downloads.mesosphere.com/dcos/" + release_name + "/aws.html")


def do_promote_candidate(options):
    """Steps:
    1) Generate new landing page
    2) Download, edit cloudformation templates to point to new url
    3) s3 copy across individual packages (Discovered through active.json)
    4) upload modified files, meta files:
        - active.json
        - bootstrap.tar.xz
        - cloudformation template
        - landing page
    """
    raise NotImplementedError()

    rc_name = 'testing/' + options.release_name

    def fetch_from_s3(name, target):
        download_s3(get_object(rc_name, name), target)

    button_page = gen_buttons(options.release_name, "DCOS " + options.release_name)
    # Download and modify cloudformation template bootstrap_url

    # TODO(cmaloney): Finish This
    upload_buttons(options.release_name, button_page)


def do_print_nat_amis(options):
    region_to_ami = {}

    for region in aws_region_names:
        ec2 = boto3.client('ec2', region_name=region['id'])

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


def do_launch(name, template_url):
    stack = boto3.resource('cloudformation').create_stack(
        DisableRollback=True,
        TimeoutInMinutes=20,
        Capabilities=['CAPABILITY_IAM'],
        Parameters=[{
            'ParameterKey': 'AcceptEULA',
            'ParameterValue': 'Yes'
        }, {
            'ParameterKey': 'KeyName',
            'ParameterValue': 'default'
        }],
        StackName=name,
        TemplateURL=template_url
        )
    print('StackId:', stack.stack_id)
    return stack


def do_wait_for_up(stack):
    shown_events = set()
    # Watch for the stack to come up. Error if steps take too long.
    print("Waiting for stack to come up")
    while(True):
        stack.reload()
        if stack.stack_status == 'CREATE_COMPLETE':
            break

        events = reversed(list(stack.events.all()))

        for event in events:
            if event.event_id in shown_events:
                continue

            shown_events.add(event.event_id)

            status = event.resource_status_reason
            if status is None:
                status = ""

            # TODO(cmaloney): Watch for Master, Slave scaling groups. When they
            # come into existence watch them for IP addresses, print the IP
            # addresses.
            # if event.logical_resource_id in ['SlaveServerGroup', 'MasterServerGroup', 'PublicSlaveServerGroup']:

            print(event.resource_status,
                  event.logical_resource_id,
                  event.resource_type,
                  status)
        time.sleep(10)

    # TODO (cmaloney): Print DnsAddress once cluster is up
    print("")
    print("")
    print("Cluster Up!")
    stack.load()  # Force the stack to update since events have happened
    for item in stack.outputs:
        if item['OutputKey'] == 'DnsAddress':
            print("DnsAddress:", item['OutputValue'])


def get_launched_clusters():
    try:
        return load_json(os.path.expanduser("~/.config/dcos-image-clusters"))
    except FileNotFoundError:
        return []


def save_launched_clusters(cluster_list):
    write_json(os.path.expanduser("~/.config/dcos-image-clusters"), cluster_list)


def do_list_clusters(options):
    print("\n".join(get_launched_clusters()))


def do_cluster_launch(options):
    template_url = None
    if options.cloudformation_url:
        template_url = options.cloudformation_url
    elif options.release_name:
        template_url = 'https://s3.amazonaws.com/downloads.mesosphere.io/dcos/' + \
                options.release_name + '/cloudformation/single-master.cloudformation.json'
    else:
        template_url = 'https://s3.amazonaws.com/downloads.mesosphere.io/dcos/' + \
                'testing/continuous/cloudformation/single-master.cloudformation.json'

    stack = do_launch(options.name, template_url)
    save_launched_clusters([options.name] + get_launched_clusters())

    do_wait_for_up(stack)


def get_cluster_name_if_unset(name):
    if not name:
        clusters = get_launched_clusters()
        if len(clusters) < 1:
            print("ERROR: No launched clusters to resume")
            sys.exit(1)
        name = clusters[0]
    return name


def delete_s3_nonempty(bucket):
    # This is an exhibitor bucket, should only have one item in it. Die hard rather
    # than accidentally doing the wrong thing if there is more.

    objects = [bucket.objects.all()]
    assert len(objects) == 1

    for obj in objects:
        obj.delete()

    bucket.delete()


def do_cluster_resume(options):
    name = get_cluster_name_if_unset(options.name)
    stack = boto3.resource('cloudformation').Stack(name)
    print("Resuming cluster", name)
    do_wait_for_up(stack)


def do_cluster_delete(options):
    name = get_cluster_name_if_unset(options.name)
    stack = boto3.resource('cloudformation').Stack(name)

    # Delete the s3 bucket
    stack_resource = stack.Resource('ExhibitorS3Bucket')
    bucket = boto3.resource('s3').Bucket(stack_resource.physical_resource_id)
    delete_s3_nonempty(bucket)

    # Delete the stack
    stack.delete()


def main():
    parser = argparse.ArgumentParser(description='AWS DCOS image+template creation, management utilities.')
    subparsers = parser.add_subparsers(title='commands')

    # build subcommand.
    build = subparsers.add_parser('build')
    build.set_defaults(func=do_build)
    build.add_argument('--upload', action='store_true')
    build.add_argument('--skip-package-build', action='store_true')
    build.add_argument('--testing-name', default='continuous')
    gen.add_arguments(parser)

    # make_candidate subcommand.
    make_candidate = subparsers.add_parser('make-candidate')
    make_candidate.set_defaults(func=do_make_candidate)
    make_candidate.add_argument('release-name')

    # promote_candidate subcommand.
    promote_candidate = subparsers.add_parser('promote-candidate')
    promote_candidate.set_defaults(func=do_promote_candidate)
    promote_candidate.add_argument('release-name')

    # print_coreos_amis subcommand.
    print_coreos_amis = subparsers.add_parser('print-coreos-amis')
    print_coreos_amis.set_defaults(func=do_print_coreos_amis)

    # print_nat_amis subcommand.
    print_nat_amis = subparsers.add_parser('print-nat-amis')
    print_nat_amis.set_defaults(func=do_print_nat_amis)

    # cluster subcommand.
    cluster = subparsers.add_parser('cluster')
    cluster_subparsers = cluster.add_subparsers(title='actions')
    cluster.set_defaults(func=do_list_clusters)
    launch = cluster_subparsers.add_parser('launch')
    release_cf_url = launch.add_mutually_exclusive_group()
    release_cf_url.add_argument('--cloudformation-url', type=str)
    release_cf_url.add_argument('--release-name', type=str)
    launch.add_argument('name', nargs='?', default='dcos-' + getpass.getuser() + '-' + uuid.uuid4().hex)
    launch.set_defaults(func=do_cluster_launch)
    resume = cluster_subparsers.add_parser('resume')
    resume.add_argument('name', nargs='?', default=None)
    resume.set_defaults(func=do_cluster_resume)
    delete = cluster_subparsers.add_parser('delete')
    delete.add_argument('name', nargs='?', default=None)
    delete.set_defaults(func=do_cluster_delete)

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
