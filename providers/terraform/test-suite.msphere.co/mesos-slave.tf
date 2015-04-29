resource "aws_instance" "mesos-slave" {
  tags {
    Name = "slave${count.index}.${var.uuid}"
    role = "slave"
    cluster_uuid = "${var.uuid}"
  }
  instance_type = "${var.aws_instance_type}"
  ami = "${lookup(var.aws_amis, var.aws_region)}"
  count = "${var.slave_count}"
  key_name = "${var.aws_key_name}"
  security_groups = ["${aws_security_group.security_group.name}"]
  connection {
    user = "core"
    key_file = "${var.aws_key_file}"
  }
  block_device {
    device_name = "/dev/sdb"
    virtual_name = "ephemeral0"
  }
  block_device {
    device_name = "/dev/sdc"
    virtual_name = "ephemeral1"
  }
  block_device {
    device_name = "/dev/sdd"
    volume_type = "gp2"
    volume_size = 100
    delete_on_termination = 1
  }
  user_data = <<CLOUD_CONFIG
#cloud-config

write_files:
  - path: /etc/mesosphere/setup-flags/repository-url
    permissions: 0644
    owner: root
    content: |
      ${var.repo_root}
  - path: /etc/mesosphere/roles/slave
  - path: /etc/mesosphere/setup-packages/dcos-config--setup/pkginfo.json
    content: '{}'
  - path: /etc/mesosphere/setup-packages/dcos-config--setup/etc/mesos-slave
    content: |
      MESOS_MASTER=zk://leader.mesos:2181/mesos
      MESOS_CONTAINERIZERS=docker,mesos
      MESOS_LOG_DIR=/var/log/mesos
      MESOS_EXECUTOR_REGISTRATION_TIMEOUT=5mins
      MESOS_ISOLATION=cgroups/cpu,cgroups/mem
      MESOS_WORK_DIR=/ephemeral/mesos-slave
      MESOS_RESOURCES=ports:[1025-2180,2182-3887,3889-5049,5052-8079,8082-65535]
      MESOS_SLAVE_SUBSYSTEMS=cpu,memory
  - path: /etc/mesosphere/setup-packages/dcos-config--setup/etc/cloudenv
    content: |
      MASTER_ELB=master0.${var.uuid}.${var.domain}
      FALLBACK_DNS=172.16.0.23
  - path: /root/.bashrc
    content: |
      export $(cat /opt/mesosphere/environment |egrep -v ^#| xargs)
  - path: /etc/mesosphere/clusterinfo.json
    permissions: 0644
    owner: root
    content: |-
      {
        "cluster":{
          "name":"${var.uuid}"
        },
        "keys":{
          "dd_api_key":"${var.dd_api_key}",
          "github_deploy_key_base64":"${var.github_deploy_key_base64}",
          "aws_access_key_id":"${var.aws_access_key_id}",
          "aws_secret_access_key":"${var.aws_secret_access_key}"
        }
      }
coreos:
  update:
    reboot-strategy: off
  etcd:
    discovery: ${var.discovery_url}
    addr: $private_ipv4:4001
    peer-addr: $private_ipv4:7001
  units:
    - name: format-ephemeral.service
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
        Type=ext4
    - name: format-docker-ephemeral.service
      command: start
      content: |
        [Unit]
        Description=Formats the docker ephemeral drive
        Before=var-lib-docker.mount
        [Service]
        Type=oneshot
        RemainAfterExit=yes
        ExecStart=/bin/bash -c '(blkid -t TYPE=btrfs | grep xvdd) || /usr/sbin/wipefs -f /dev/xvdd; /usr/sbin/mkfs.btrfs -f /dev/xvdd'
    - name: var-lib-docker.mount
      command: start
      content: |
        [Unit]
        Description=Mount ephemeral to /var/lib/docker
        Before=docker.service
        [Mount]
        What=/dev/xvdd
        Where=/var/lib/docker
        Type=btrfs
    - name: systemd-resolved.service
      command: stop
    - name: etcd.service
      mask: true
      command: stop
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
    - name: link-env.service
      command: start
      content: |
        [Service]
        Type=oneshot
        Before=dcos.target
        ExecStartPre=/usr/bin/mkdir -p /etc/profile.d
        ExecStart=/usr/bin/ln -s /opt/mesosphere/environment.export /etc/profile.d/dcos.sh
    - name: dcos-download.service
      content: |
        [Unit]
        Description=Download the DCOS
        After=network-online.target
        Wants=network-online.target
        ConditionPathExists=!/opt/mesosphere/
        [Service]
        Type=oneshot
        ExecStartPre=/usr/bin/curl --retry 100 ${var.repo_root}/bootstrap.tar.xz -o /tmp/bootstrap.tar.xz
        ExecStartPre=/usr/bin/mkdir -p /opt/mesosphere
        ExecStart=/usr/bin/tar -xf /tmp/bootstrap.tar.xz -C /opt/mesosphere
    - name: dcos-setup.service
      command: start
      enable: true
      content: |
        [Unit]
        Description=Prep the Pkgpanda working directories for this host.
        Requires=dcos-download.service
        After=dcos-download.service
        [Service]
        Type=oneshot
        EnvironmentFile=/opt/mesosphere/environment
        ExecStart=/opt/mesosphere/bin/pkgpanda setup
        [Install]
        WantedBy=multi-user.target
    - name: datadog.service
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
        -e API_KEY=${var.dd_api_key} \
        mesosphere/dd-agent-mesos-slave"
CLOUD_CONFIG
}
