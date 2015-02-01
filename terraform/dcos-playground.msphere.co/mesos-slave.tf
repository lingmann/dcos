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
    device_name = "/dev/sda"
    volume_type = "gp2"
    volume_size = 32
    delete_on_termination = 1
  }
  user_data = <<CLOUD_CONFIG_SLAVE
#cloud-config
coreos:
  update:
    reboot-strategy: best-effort
  etcd:
    discovery: ${var.discovery_url}
    addr: $private_ipv4:4001
    peer-addr: $private_ipv4:7001
  units:
    - name: etcd.service
      command: start
    - name: fleet.service
      command: start
    - name: systemd-resolved.service
      command: reload-or-restart
    - name: bootstrap.service
      command: start
      content: |
        [Unit]
        Description=Bootstrap DCOS
        [Service]
        Type=oneshot
        RemainAfterExit=yes
        ExecStartPre=/usr/bin/wget -nv https://s3.amazonaws.com/downloads.mesosphere.io/dcos/bootstrap.sh -O /bootstrap.sh
        ExecStartPre=/usr/bin/chmod +x /bootstrap.sh
        ExecStart=/bootstrap.sh
    - name: mesos-slave.service
      command: start
      content: |
        [Unit]
        Description=Mesos Slave
        After=bootstrap.service
        Requires=bootstrap.service
        [Service]
        Restart=on-failure
        EnvironmentFile=/etc/environment
        ExecStart=/opt/mesosphere/dcos/latest/mesos/sbin/mesos-slave --master=zk://${aws_instance.mesos-master.private_ip}:2181/mesos --containerizers=docker,mesos --hostname=slave${count.index}.${var.uuid}.${var.domain} --log_dir=/var/log/mesos --executor_registration_timeout=5mins --isolation=cgroups/cpu,cgroups/mem --work_dir=/var/lib/mesos/slave
  fleet:
    metadata: role=slave
CLOUD_CONFIG_SLAVE
}
