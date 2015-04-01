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
  user_data = <<CLOUD_CONFIG
#cloud-config

write_files:
  - path: /etc/mesosphere/setup-flags/repository-url
    permissions: 0644
    owner: root
    content: |
      ${var.repo_root}
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
      MESOS_LOG_DIR=/var/log/mesos
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
        ExecStartPre=/usr/bin/curl ${var.repo_root}bootstrap.tar.xz -o /tmp/distribution.tar.xz
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
CLOUD_CONFIG
}
