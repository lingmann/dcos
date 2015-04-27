import json
import re

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from pkgpanda.util import load_json, write_string

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


def render_parameter(simple, name):
    if simple:
        return start_param_simple + name + end_param_simple
    return start_param_full + name + end_param_full


def render_cloudformation(simple, master_cloudconfig, slave_cloudconfig, bootstrap_url):
    # TODO(cmaloney): There has to be a cleaner way to do this transformation.
    # For now just moved from cloud_config_cf.py
    # TODO(cmaloney): Move with the logic that does this same thing in Azure
    def transform_lines(text):
        return ''.join(map(transform, text.splitlines())).rstrip(',\n')

    template_str = cloudformation_template.render({
        'master_cloud_config': transform_lines(master_cloudconfig),
        'slave_cloud_config': transform_lines(slave_cloudconfig),
        'start_param': start_param_simple if simple else start_param_full,
        'end_param': end_param_simple if simple else end_param_full
    })

    write_string('temp', template_str)

    template_json = json.loads(template_str)

    params['BootstrapRepoRoot']['Default'] = bootstrap_url

    for param, info in params.items():
        if simple:
            if 'Parameters' not in template_json['Mappings']:
                template_json['Mappings']['Parameters'] = {}
            template_json['Mappings']['Parameters'][param] = {'default': info['Default']}
        else:
            template_json['Parameters'][param] = info

    return json.dumps(template_json)


def render_buttons(name):
    return launch_template.render({
        'regions': [
            'us-west-1',
            'us-west-2',
            'us-east-1',
            'sa-east-1',
            'eu-west-1',
            'eu-central-1',
            'ap-northeast-1',
            'ap-southeast-1',
            'ap-southeast-2'
            ],
        'name': name
        })
