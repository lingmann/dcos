def extra_files(master_count):
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
""".format(master_count=master_count)

stack_name = '{ "Ref" : "AWS::StackName" }'

early_units = """
    - name: format-var-lib-ephemeral.service
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

config_writer = """
    - name: config-writer.service
      command: start
      content: |
        [Unit]
        Description=Write out dynamic config values
        [Service]
        Type=oneshot
        ExecStart=/usr/bin/bash -c "echo EXHIBITOR_HOSTNAME=$(curl -s http://169.254.169.254/latest/meta-data/public-hostname) >> /etc/mesosphere/setup-packages/dcos-config--setup/etc/cloudenv"
        ExecStart=/usr/bin/bash -c "echo MARATHON_HOSTNAME=$(curl -s http://169.254.169.254/latest/meta-data/public-hostname) >> /etc/mesosphere/setup-packages/dcos-config--setup/etc/cloudenv"
        ExecStart=/usr/bin/bash -c "echo MESOS_HOSTNAME=$(curl -s http://169.254.169.254/latest/meta-data/public-hostname) >> /etc/mesosphere/setup-packages/dcos-config--setup/etc/mesos-master"
        ExecStart=/usr/bin/bash -c "echo MESOS_HOSTNAME=$(curl -s http://169.254.169.254/latest/meta-data/public-hostname) >> /etc/mesosphere/setup-packages/dcos-config--setup/etc/mesos-slave"
"""


def late_units(roles):
    return """
    - name: cfn-signal.service
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
        ExecStartPre=/usr/bin/docker run --rm mbabineau/cfn-bootstrap \
          cfn-signal -e 0 \
          --resource {report_name} \
          --stack {{ "Ref" : "AWS::StackName" }} \
          --region {{ "Ref" : "AWS::Region" }}
        ExecStart=/usr/bin/touch /var/lib/cfn-signal
""".format(report_name='MasterServerGroup' if 'master' in roles else 'SlaveServerGroup')
