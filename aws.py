#!/usr/bin/env python3
"""AWS Image Creation, Management, Testing

Usage:
    #NOTE: This should do the cf template validation using boto.
    aws.py build [--upload] [--skip-package-build]
    aws.py promote <from_release> <to_release>
    aws.py release
    aws.py test (build|--release=<release_name>) <name>
    aws.py test resume
    aws.py cluster delete
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

env = jinja2.Environment(
        undefined=jinja2.StrictUndefined)

params = load_json("gen/aws/cf_param_info.json")

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
    template_str = env.from_string(cf_template).render({
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


def do_upload(release_name, bootstrap_id, config_package_id, cloudformation_text):
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

    # Upload the cloudformation package
    # Caclulate cloudformation template id (sha1 of contents)
    cf_bytes = cloudformation_text.encode('utf-8')
    hasher = hashlib.sha1()
    hasher.update(cf_bytes)
    cf_id = binascii.hexlify(hasher.digest()).decode('ascii')
    cf_object = get_object(release_name, 'cloudformation/{}.cloudformation.json'.format(cf_id))
    cf_object.put(Body=cf_bytes)

    return 'https://s3.amazonaws.com/downloads.mesosphere.io/{}'.format(cf_object.key)


def do_build(args):
    # TODO(cmaloney): don't shell out to mkpanda
    if not args.skip_package_build:
        check_call(['mkpanda', 'tree', '--mkbootstrap'], cwd='packages', env=base_env)

    bootstrap_id = load_string('packages/bootstrap.latest')

    release_name = 'testing/' + args.testing_name

    results = gen.generate(
        options=args,
        mixins=['aws', 'coreos', 'coreos-aws'],
        extra_templates={'cloudformation': ['gen/aws/templates/cloudformation.json']},
        arguments={'bootstarp_id': bootstrap_id, 'release_name': release_name}
        )

    cloud_config = results['templates']['cloud-config']

    # Add general services
    cloud_config = results['utils'].add_services(cloud_config)

    # Specialize for master, fslave, public_slave
    variant_cloudconfig = {}
    for variant, params in cf_instance_groups.items():
        cc_variant = deepcopy(cloud_config)

        # Specialize the cfn-signal service
        cc_variant = results['utils'].add_units(
            cc_variant,
            yaml.load(env.from_string(late_services).render(params)))

        # Add roles
        cc_variant = results['utils'].add_roles(cc_variant, params['roles'] + ['aws'])

        # NOTE: If this gets printed in string stylerather than '|' the AWS
        # parameters which need to be split out for the cloudformation to
        # interpret end up all escaped and undoing it would be hard.
        variant_cloudconfig[variant] = results['utils'].render_cloudconfig(cc_variant)

    # Render the cloudformation
    cloudformation = render_cloudformation(
        results['templates']['cloudformation'],
        variant_cloudconfig['master'],
        variant_cloudconfig['slave'],
        variant_cloudconfig['public_slave']
        )

    print("Validating CloudFormation")
    client = boto3.client('cloudformation')
    client.validate_template(TemplateBody=cloudformation)

    # TODO(cmaloney): print out the final cloudformation s3 path.
    if args.upload:
        cf_path = do_upload(release_name, bootstrap_id, results['arguments']['config_package_id'], cloudformation)
        print("CloudFormation to launch: ", cf_path)
    return cf_path


def main():
    parser = argparse.ArgumentParser('AWS DCOS template creation, management utilities.')
    subparsers = parser.add_subparsers(title='subcommands')
    build_parser = subparsers.add_parser('build')
    build_parser.set_defaults(func=do_build)
    add_build_arguments(build_parser)
    args = parser.parse_args()

    # Use an if rather than try/except since lots of things inside could throw
    # an AttributeError.
    if hasattr(args, 'func'):
        args.func(args)
        sys.exit(0)
    else:
        parser.print_help()
        print("ERROR: Must use a subcommand")
        sys.exit(1)


if __name__ == '__main__':
    main()
