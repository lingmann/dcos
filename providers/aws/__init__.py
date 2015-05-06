import json
import re

from copy import copy
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from pkgpanda.util import load_json, write_string
from cloud_config_parameters import CloudConfigParameters

AWS_REF_REGEX = re.compile(r"(?P<before>.*)(?P<ref>{ .* })(?P<after>.*)")

start_param_simple = '{ "Fn::FindInMap" : [ "Parameters", "'
end_param_simple = '", "default" ] }'
start_param_full = '{ "Ref" : "'
end_param_full = '" }'

# NOTE: Strict undefined behavior since we're doing generation / validation here.
env = Environment(loader=FileSystemLoader('aws/templates'), undefined=StrictUndefined)
launch_template = env.get_template('launch_buttons.md')
params = load_json("aws/cf_param_info.json")
testcluster_params = load_json("aws/testcluster_param_info.json")
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


def render_cloudformation(simple, master_cloudconfig, slave_cloudconfig, public_slave_cloudconfig, bootstrap_url, testcluster):
    # TODO(cmaloney): There has to be a cleaner way to do this transformation.
    # For now just moved from cloud_config_cf.py
    # TODO(cmaloney): Move with the logic that does this same thing in Azure
    def transform_lines(text):
        return ''.join(map(transform, text.splitlines())).rstrip(',\n')

    template_str = cloudformation_template.render({
        'master_cloud_config': transform_lines(master_cloudconfig),
        'slave_cloud_config': transform_lines(slave_cloudconfig),
        'public_slave_cloud_config': transform_lines(public_slave_cloudconfig),
        'start_param': start_param_simple if simple else start_param_full,
        'end_param': end_param_simple if simple else end_param_full
    })

    write_string('temp', template_str)

    template_json = json.loads(template_str)

    params['BootstrapRepoRoot']['Default'] = bootstrap_url

    local_params = copy(params)

    if testcluster:
        local_params.update(testcluster_params)

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


class Parameters(CloudConfigParameters):

    def __init__(self, simple, roles):
        self._simple = simple
        self.roles = roles
        self._testcluster_volume = False

        # Can only be master or slave currently because of stuff in
        # late_units for cfn signaling
        assert len(roles) == 1

    @property
    def extra_files_base(self):
        return """
  - path: /etc/mesosphere/setup-packages/dcos-config--setup/etc/cloudenv
    content: |
      AWS_REGION={{ "Ref" : "AWS::Region" }}
      AWS_ACCESS_KEY_ID={{ "Ref" : "HostKeys" }}
      AWS_SECRET_ACCESS_KEY={{ "Fn::GetAtt" : [ "HostKeys", "SecretAccessKey" ] }}
      ZOOKEEPER_CLUSTER_SIZE={master_count}
      MASTER_ELB={{ "Fn::GetAtt" : [ "InternalMasterLoadBalancer", "DNSName" ] }}
      # Must set FALLBACK_DNS to an AWS region-specific DNS server which returns
      # the internal IP when doing lookups on AWS public hostnames.
      FALLBACK_DNS=10.0.0.2
  - path: /etc/mesosphere/setup-packages/dcos-config--setup/etc/exhibitor
    content: |
      AWS_S3_BUCKET={{ "Ref" : "ExhibitorS3Bucket" }}
      AWS_S3_PREFIX={{ "Ref" : "AWS::StackName" }}
      EXHIBITOR_WEB_UI_PORT=8181
""".format(master_count=render_parameter(self._simple, 'MasterInstanceCount'))

    @property
    def stack_name(self):
        return '{ "Ref" : "AWS::StackName" }'

    @property
    def early_units(self):
        result = """    - name: format-var-lib-ephemeral.service
      command: start
      content: |
        [Unit]
        Description=Formats the /var/lib ephemeral drive
        Before=var-lib.mount dbus.service
        [Service]
        Type=oneshot
        RemainAfterExit=yes
        ExecStart=/bin/bash -c '(blkid -t TYPE=ext4 | grep xvdb) || (/usr/sbin/mkfs.ext4 -F /dev/xvdb)'
    - name: var-lib.mount
      command: start
      content: |
        [Unit]
        Description=Mount /var/lib
        Before=dbus.service
        [Mount]
        What=/dev/xvdb
        Where=/var/lib
        Type=ext4
"""
        if self._testcluster_volume:
            result += """    - name: format-ephemeral.service
      command: start
      content: |
        [Unit]
        Description=Formats the ephemeral drive
        Before=ephemeral.mount
        [Service]
        Type=oneshot
        RemainAfterExit=yes
        ExecStart=/bin/sh -c 'mdadm --stop /dev/md/* ; true'
        ExecStart=/usr/sbin/mdadm --create -f -R /dev/md0 --level=0 --raid-devices=2 /dev/xvdb /dev/xvdc
        ExecStart=/bin/bash -c '(blkid -t TYPE=ext4 | grep md0) || /usr/sbin/mkfs.ext4 /dev/md0'
    - name: ephemeral.mount
      command: start
      content: |
        [Unit]
        Description=Ephemeral Mount
        [Mount]
        What=/dev/md0
        Where=/ephemeral
        Type=ext4"""
        return result

    @property
    def config_writer(self):
        return """    - name: config-writer.service
      command: start
      content: |
        [Unit]
        Description=Write out dynamic config values
        [Service]
        Type=oneshot
        ExecStart=/usr/bin/bash -c "echo EXHIBITOR_HOSTNAME=$(curl -s http://169.254.169.254/latest/meta-data/hostname) >> /etc/mesosphere/setup-packages/dcos-config--setup/etc/cloudenv"
        ExecStart=/usr/bin/bash -c "echo MARATHON_HOSTNAME=$(curl -s http://169.254.169.254/latest/meta-data/hostname) >> /etc/mesosphere/setup-packages/dcos-config--setup/etc/cloudenv"
        ExecStart=/usr/bin/bash -c "echo MESOS_HOSTNAME=$(curl -s http://169.254.169.254/latest/meta-data/hostname) >> /etc/mesosphere/setup-packages/dcos-config--setup/etc/mesos-master"
        ExecStart=/usr/bin/bash -c "echo MESOS_HOSTNAME=$(curl -s http://169.254.169.254/latest/meta-data/hostname) >> /etc/mesosphere/setup-packages/dcos-config--setup/etc/mesos-slave"
"""

    @property
    def late_units_base(self):
        if 'master' in self.roles:
            report_name = 'MasterServerGroup'
        elif 'slave' in self.roles:
            report_name = 'SlaveServerGroup'
        else:
            report_name = 'PublicSlaveServerGroup'
        return """    - name: cfn-signal.service
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
          --resource {report_name} \\
          --stack {{ "Ref": "AWS::StackName" }} \\
          --region {{ "Ref" : "AWS::Region" }}
        ExecStart=/usr/bin/touch /var/lib/cfn-signal
""".format(report_name=report_name)

    def GetParameter(self, name):
        if name == 'stack_name':
            return '{ "Ref" : "AWS::StackName" }'

        real_name = {
            'bootstrap_url': 'BootstrapRepoRoot',
            'master_quorum': 'MasterQuorumCount',
            'dd_api_key': 'DatadogApiKey',
            'github_deploy_key_base64': 'GithubDeployKeyBase64'
        }[name]

        return render_parameter(self._simple, real_name)

    def AddTestclusterEphemeralVolume(self):
        # Should only ever be called once.
        assert not self._testcluster_volume
        self._testcluster_volume = True
