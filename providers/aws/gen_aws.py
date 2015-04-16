#!/usr/bin/env python2
"""
Usage:

gen_aws [<default_bootstrap_root>]
"""

import json
import re
import sys

from jinja2 import Environment, FileSystemLoader

AWS_REF_REGEX = re.compile(r"(?P<before>.*)(?P<ref>{ .* })(?P<after>.*)")


def escape_cloud_config(content_str):
    return json.dumps(content_str)


def transform(line):
    m = AWS_REF_REGEX.search(line)
    # no splitting necessary
    if not m:
        return "%s,\n" % (json.dumps(line))

    before = m.group('before')
    ref = m.group('ref')
    after = m.group('after')

    transformed_before = "%s" % (json.dumps(before))
    transformed_ref = ref
    transformed_after = "%s" % (json.dumps(after))
    return "%s, %s, %s, %s,\n" % (transformed_before, transformed_ref, transformed_after, '"\\n"')


env = Environment(loader=FileSystemLoader('jinja2'))
cloud_config_template = env.get_template("cloud-config.yaml")
launch_template = env.get_template('launch_buttons.md')


def render_cloudconfig(roles, simple):
    def make_aws_param(name):
        if simple:
            return '{ "Ref" : "' + name + '" }'
        return '{ "Fn::FindInMap" : [ "Parameters", "' + name + '", "default" ] }'

    assert type(roles) == list
    return cloud_config_template.render({
        'bootstrap_url': make_aws_param('BootstrapRepoRoot'),
        'roles': roles,
        'master_quorum': make_aws_param('MasterQuorumCount'),
        'master_count': make_aws_param('MasterInstanceCount')})


def render_cloudformation(template, simple, default_repo_url):
    # TODO(cmaloney): There has to be a cleaner way to do this transformation.
    # For now just moved from cloud_config_cf.py
    def transform_lines(text):
        return ''.join(map(transform, text.splitlines())).rstrip(',\n')

    return template.render({
        'default_repo_url': default_repo_url,
        'master_cloud_config': transform_lines(render_cloudconfig(['master'], simple)),
        'slave_cloud_config': transform_lines(render_cloudconfig(['slave'], simple))
        })


def output_string(filename, data):
    with open(filename, 'w+') as f:
        f.write(data)


def output_template(name, simple, default_repo_url):
    output_string(name, render_cloudformation(env.get_template(name), simple, default_repo_url))

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("USAGE: gen_aws <base_url> <name>")
        sys.exit(1)

    base_url = sys.argv[1]
    name = sys.argv[2]

    # base_url must end in '/'
    assert base_url[-1] == '/'

    # Name shouldn't start or end with '/'
    assert name[0] != '/'
    assert name[-1] != '/'

    default_repo_url = base_url + name

    default_bootstrap_root = sys.argv[1]
    output_template('unified.json', False, default_repo_url)
    output_template('simple-unified.json', True, default_repo_url)
    output_string('launch_buttons.md', launch_template.render({
        'regions': [
            'eu-central-1',
            'ap-northeast-1',
            'sa-east-1',
            'ap-southeast-2',
            'ap-southeast-1',
            'us-east-1',
            'us-west-2',
            'us-west-1',
            'eu-west-1'],
        'name': name
        }))
