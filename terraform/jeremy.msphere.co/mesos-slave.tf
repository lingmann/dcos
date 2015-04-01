resource "aws_instance" "mesos-slave" {
  tags {
    Name = "slave${count.index}.${var.uuid}"
    role = "slave"
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
  user_data = <<CLOUD_CONFIG
#cloud-config

write_files:
  - path: /etc/systemd/network/aws-ec2.network
    content: |
      [Match]
      Name=eth0
      [Network]
      DHCP=v4
      [DHCP]
      UseMTU=true
      UseDNS=false
      UseDomains=false
  - path: /etc/systemd/resolved.conf.d/mesos-dns.conf
    content: |
      [Resolve]
      FallbackDNS=172.16.0.23
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
      MESOS_WORK_DIR=/var/lib/mesos/slave
  - path: /etc/mesosphere/setup-packages/dcos-config--setup/etc/cloudenv
    content: |
      MASTER_ELB=master0.${var.uuid}.${var.domain}
      FALLBACK_DNS=172.16.0.23
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
    - name: systemd-resolved.service
      command: restart
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
        ExecStart=/usr/bin/bash -c "echo MESOS_HOSTNAME=$(curl -s http://169.254.169.254/latest/meta-data/public-hostname) >> /etc/mesosphere/setup-packages/dcos-config--setup/etc/mesos-slave"
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
