#!/usr/bin/env python3
"""Generate provider-specific templates, data.
Usage:
gen.py [aws|testcluster] <base_url> <name>

"""
import json
from docopt import docopt
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from pkgpanda.util import write_json, write_string
from string import Template

import aws

# NOTE: Strict undefined behavior since we're doing generation / validation here.
env = Environment(loader=FileSystemLoader('templates'), undefined=StrictUndefined)
cc_template = env.get_template('cloud-config.yaml')


def render_cloudconfig(paramters):
    return cc_template.render({
        'bootstrap_url': paramters.GetParameter('bootstrap_url'),
        'roles': paramters.roles,
        'master_quorum': paramters.GetParameter('master_quorum'),
        'extra_files': paramters.extra_files,
        'stack_name': paramters.GetParameter('stack_name'),
        'early_units': paramters.early_units,
        'config_writer': paramters.config_writer,
        'late_units': paramters.late_units
        })


def add_testcluster(parameters):
    parameters.AddTestclusterEphemeralVolume()
    # NOTE: Using python Template instead of .format to escape
    # escaping hell.
    parameters.extra_files_extra += Template("""  - path: /etc/mesosphere/clusterinfo.json
    permissions: 0644
    owner: root
    content: |-
      {
        "cluster":{
          "name":"$name"
        },
        "keys":{
          "dd_api_key":"$dd_api_key",
          "github_deploy_key_base64":"$github_deploy_key_base64"
        }
      }""").substitute(
        name=parameters.GetParameter('stack_name'),
        dd_api_key=parameters.GetParameter('dd_api_key'),
        github_deploy_key_base64=parameters.GetParameter('github_deploy_key_base64')
      )

    parameters.late_units_extra = """    - name: datadog.service
      command: start
      content: |
        [Unit]
        Description=Monitoring Service
        [Service]
        TimeoutStartSec=0
        Restart=on-failure
        ExecStartPre=-/usr/bin/docker kill dd-agent
        ExecStartPre=-/usr/bin/docker rm dd-agent
        ExecStartPre=/usr/bin/docker pull mesosphere/dd-agent-mesos-slave
        ExecStart=/usr/bin/bash -c \
        "/usr/bin/docker run --privileged --name dd-agent --net=host \
        -v /var/run/docker.sock:/var/run/docker.sock \
        -v /proc/mounts:/host/proc/mounts:ro \
        -v /sys/fs/cgroup/:/host/sys/fs/cgroup:ro \
        -e API_KEY={0} \
        mesosphere/dd-agent-mesos-slave" """.format(parameters.GetParameter('dd_api_key'))


# TODO(cmaloney): Minimize amount of code in this function. All
# providers should be as simple as possible.
def gen_aws(name, bootstrap_url):

    # TODO(cmaloney): That we talk about 'testcluster' here is wrong.
    # We should just talk about 'extra parameters'.
    def aws_cloudformation(simple, testcluster=False):
        def get_params(roles):
            parameters = aws.Parameters(simple, roles)
            if testcluster:
                add_testcluster(parameters)
            return parameters

        return aws.render_cloudformation(
            simple,
            render_cloudconfig(get_params(['master'])),
            render_cloudconfig(get_params(['slave'])),
            bootstrap_url,
            testcluster
            )

    # Parameterized / custom template.
    write_string('cloudformation.json', aws_cloudformation(False))
    write_string('testcluster.cloudformation.json', aws_cloudformation(False, True))

    # Simple template.
    single_master_cf = aws_cloudformation(True)
    write_string('single-master.cloudformation.json', single_master_cf)

    # Simple 3 master.
    # Transform 1-master into having 3 masters in the scaling group.
    cf_multimaster = json.loads(single_master_cf)
    cf_multimaster['Mappings']['Parameters']['MasterQuorumCount']['default'] = 2
    cf_multimaster['Mappings']['Parameters']['MasterInstanceCount']['default'] = 3
    write_json('multi-master.cloudformation.json', cf_multimaster)

    # Create the aws launch button page
    write_string('aws.md', aws.render_buttons(name))


def main():
    arguments = docopt(__doc__)

    do_gen_aws = False
    base_url = arguments['<base_url>']
    name = arguments['<name>']

    # TODO(cmaloney): Make more human error messages
    # base_url must end in '/'
    assert base_url[-1] == '/'

    # Name shouldn't start or end with '/'
    assert name[0] != '/'
    assert name[-1] != '/'

    bootstrap_url = base_url + name

    if arguments['aws']:
        do_gen_aws = True
    else:
        do_gen_aws = True

    if do_gen_aws:
        gen_aws(name, bootstrap_url)

if __name__ == '__main__':
    main()
