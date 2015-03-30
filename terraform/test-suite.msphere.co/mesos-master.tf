resource "aws_instance" "mesos-master" {
  tags {
    Name = "master${count.index}.${var.uuid}"
    role = "master"
  }
  instance_type = "${var.aws_instance_type}"
  ami = "${lookup(var.aws_amis, var.aws_region)}"
  count = "${var.master_count}"
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
    permission: 0644
    owner: root
    content: |
      http://s3.amazonaws.com/downloads.mesosphere.io/dcos/pkgpanda/
  - path: /etc/mesosphere/roles/master
  - path: /etc/mesosphere/setup-packages/dcos-config--setup/pkginfo.json
    content: '{}'
  - path: /etc/mesosphere/setup-packages/dcos-config--setup/etc/mesos-dns.json
    content: |
      {
        "zk": "zk://127.0.0.1:2181/mesos",
        "refreshSeconds": 60,
        "ttl": 60,
        "domain": "mesos",
        "port": 53,
        "resolvers": ["172.16.0.23"],
        "timeout": 5,
        "listener": "0.0.0.0",
        "email": "root.mesos-dns.mesos"
      }
  - path: /etc/mesosphere/setup-packages/dcos-config--setup/etc/mesos-master
    content: |
      MESOS_WORK_DIR=/var/lib/mesos/master
      MESOS_ZK=zk://127.0.0.1:2181/mesos
      MESOS_QUORUM=${var.mesos_master_quorum}
      MESOS_CLUSTER=${var.uuid}.${var.domain}
  - path: /etc/mesosphere/setup-packages/dcos-config--setup/etc/cloudenv
    content: |
      AWS_REGION=${var.aws_region}
      AWS_ACCESS_KEY_ID=${var.aws_access_key}
      AWS_SECRET_ACCESS_KEY=${var.aws_secret_key}
      ZOOKEEPER_CLUSTER_SIZE=${var.master_count}
  - path: /etc/mesosphere/setup-packages/dcos-config--setup/etc/zookeeper
    content: |
      S3_BUCKET=${var.exhibitor_s3_bucket}
      S3_PREFIX=${var.uuid}
      EXHIBITOR_WEB_UI_PORT=8181
  - path: /root/.bashrc
    content: |
      export $(cat /opt/mesosphere/environment |egrep -v ^#| xargs)
coreos:
  update:
    reboot-strategy: off
  etcd:
    discovery: ${var.discovery_url}
    addr: $private_ipv4:4001
    peer-addr: $private_ipv4:7001
  units:
    - name: format-var-lib-ephemeral.service
      command: start
      content: |
        [Unit]
        Description=Formats the /var/lib ephemeral drive
        Before=var-lib.mount,dbus.service
        [Service]
        Type=oneshot
        RemainAfterExit=yes
        ExecStart=/bin/sh -c 'mdadm --stop /dev/md/* ; true'
        ExecStart=/usr/sbin/mdadm --create -f -R /dev/md0 --level=0 --raid-devices=2 /dev/xvdb /dev/xvdc
        ExecStart=/usr/sbin/mkfs.ext4 /dev/md0
    - name: var-lib.mount
      command: start
      content: |
        [Unit]
        Description=Mount /var/lib
        Before=dbus.service
        [Mount]
        What=/dev/md0
        Where=/var/lib
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
        ExecStart=/usr/sbin/wipefs -f /dev/xvdd
        ExecStart=/usr/sbin/mkfs.btrfs -f /dev/xvdd
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
        ExecStart=/usr/bin/bash -c "echo EC2_PUBLIC_HOSTNAME=$(curl -s http://169.254.169.254/latest/meta-data/public-hostname) >> /etc/mesosphere/setup-packages/dcos-config--setup/etc/cloudenv"
        ExecStart=/usr/bin/bash -c "echo MESOS_HOSTNAME=$(curl -s http://169.254.169.254/latest/meta-data/public-hostname) >> /etc/mesosphere/setup-packages/dcos-config--setup/etc/mesos-master"
    - name: dcos-setup.service
      command: start
      content: |
        [Unit]
        Description=Prep the Pkgpanda working directories for this host.
        Requires=dcos-download.service
        After=dcos-download.service
        Requires=config-writer.service
        After=config-writer.service
        ConditionPathExists=/opt/mesosphere/bootstrap
        [Service]
        Type=oneshot
        EnvironmentFile=/opt/mesosphere/environment
        ExecStartPre=/usr/bin/mkdir -p /etc/systemd/system/multi-user.target.wants
        ExecStartPre=/usr/bin/cp /etc/systemd/system/dcos.target /etc/systemd/system/multi-user.target.wants
        ExecStartPre=-/usr/bin/ln -s /opt/mesosphere/dcos.target.wants /etc/systemd/system/dcos.target.wants
        ExecStart=/opt/mesosphere/bin/pkgpanda setup --no-block-systemd
        ExecStart=/usr/bin/rm /opt/mesosphere/bootstrap
    - name: dcos-download.service
      command: start
      content: |
        [Unit]
        Description=Download the DCOS
        After=network-online.target
        Wants=network-online.target
        ConditionPathExists=!/opt/mesosphere/
        [Service]
        Type=oneshot
        ExecStartPre=/usr/bin/curl ${var.bootstrap_url} -o /tmp/distribution.tar.xz
        ExecStartPre=/usr/bin/mkdir -p /opt/mesosphere
        ExecStart=/usr/bin/tar -axf /tmp/distribution.tar.xz -C /opt/mesosphere
    - name: dcos-repair.service
      command: start
      content: |
        [Unit]
        Description=Finish a partially-completed pkgpanda upgrade swap
        ConditionPathExists=/opt/mesosphere
        ConditionPathExists=/opt/mesosphere/install_progress
        [Service]
        Type=oneshot
        EnvironmentFile=/opt/mesosphere/environment
        ExecStart=/opt/mesosphere/bin/pkgpanda activate --recover
    - name: dcos.target
      content: |
        [Unit]
        After=dcos-repair.service
        Requires=dcos-repair.service
        After=dcos-setup.service
        Requires=dcos-setup.service
    - name: datadog.service
      command: start
      content: |
        [Unit]
        Description=Monitoring Service
        [Service]
        TimeoutStartSec=0
        ExecStartPre=-/usr/bin/docker kill dd-agent
        ExecStartPre=-/usr/bin/docker rm dd-agent
        ExecStartPre=/usr/bin/docker pull mesosphere/dd-agent-mesos-master
        ExecStart=/usr/bin/bash -c \
        "/usr/bin/docker run --privileged --name dd-agent --net=host \
        -v /var/run/docker.sock:/var/run/docker.sock \
        -v /proc/mounts:/host/proc/mounts:ro \
        -v /sys/fs/cgroup/:/host/sys/fs/cgroup:ro \
        -e API_KEY=${var.dd_api_key} \
        mesosphere/dd-agent-mesos-master"
CLOUD_CONFIG
}
