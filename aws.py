#!/usr/bin/env python3
"""AWS Image Creation, Management, Testing

Usage:
    aws.py build [--upload] [--skip-package-build]
    # promote_candidate <release_name> instead?
    aws.py make_candidate <release_name>
    aws.py promote_candidate <release_name>
    aws.py promote <from_release> <to_release>
    aws.py test_release <release_name> <name>
    aws.py test <name> [--cf-url=<url>]
    aws.py test resume # Reads last test launched stack name out of file.
    aws.py cluster delete <name>
"""
import argparse
import binascii
import boto3
import hashlib
import jinja2
import json
import os
import re
import sys
import yaml
from copy import copy, deepcopy
from datetime import datetime
from pkgpanda import PackageId
from pkgpanda.util import load_json, load_string
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


def add_build_arguments(parser):
    parser.add_argument('--upload', action='store_true')
    parser.add_argument('--skip-package-build', action='store_true')
    parser.add_argument('--testing_name', default='continuous')
    gen.add_arguments(parser)


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

    # Generate the button page.
    button_page = jinja_env.from_string(open('gen/aws/templates/aws.html').read()).render({
        'release_name': release_name,
        'regions': aws_region_names
        })

    # Upload the packages.
    upload_packages(
            release_name,
            bootstrap_id,
            single_master.results.arguments['config_package_id'])
    upload_cf(release_name, 'single-master', single_master.cloudformation)
    upload_cf(release_name, 'multi-master', multi_master.cloudformation)

    # Upload button page
    get_object(release_name, 'aws.html').put(
        Body=button_page.encode('utf-8'), CacheControl='no-cache', ContentType='text/html')

    print("Candidate availabel at: https://downloads.mesosphere.com/dcos/" + release_name + "/aws.html")


def main():
    parser = argparse.ArgumentParser(description='AWS DCOS image+template creation, management utilities.')
    subparsers = parser.add_subparsers(title='subcommands')
    build_parser = subparsers.add_parser('build')
    build_parser.set_defaults(func=do_build)
    add_build_arguments(build_parser)
    candidate_parser = subparsers.add_parser('make_candidate')
    candidate_parser.set_defaults(func=do_make_candidate)
    candidate_parser.add_argument('release_name')
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
