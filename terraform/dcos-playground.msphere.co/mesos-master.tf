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
    device_name = "/dev/sda"
    volume_type = "gp2"
    volume_size = 16
    delete_on_termination = 1
  }
  user_data = <<CLOUD_CONFIG_MASTER
#cloud-config
coreos:
  update:
    reboot-strategy: etcd-lock
  etcd:
    discovery: ${var.discovery_url}
    addr: $private_ipv4:4001
    peer-addr: $private_ipv4:7001
  units:
    - name: etcd.service
      command: start
    - name: fleet.service
      command: start
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
    - name: zookeeper.service
      command: start
      content: |
        [Unit]
        Description=Zookeeper
        After=bootstrap.service
        Requires=bootstrap.service
        [Service]
        Restart=on-failure
        Environment=SYSTEMD_LOG_LEVEL=debug
        Environment=JAVA_HOME=/opt/mesosphere/dcos/latest/java
        ExecStart=/opt/mesosphere/dcos/latest/zookeeper/bin/zkServer.sh start-foreground
    - name: mesos-master.service
      command: start
      content: |
        [Unit]
        Description=Mesos Master
        After=zookeeper.service
        Requires=zookeeper.service
        [Service]
        Restart=on-failure
        EnvironmentFile=/etc/environment
        ExecStart=/opt/mesosphere/dcos/latest/mesos/sbin/mesos-master --log_dir=/var/log/mesos --work_dir=/var/lib/mesos/master --zk=zk://$private_ipv4:2181/mesos --hostname=master${count.index}.${var.uuid}.${var.domain} --cluster=${var.uuid}.${var.domain} --quorum=${var.mesos_master_quorum}
    - name: marathon.service
      command: start
      content: |
        [Unit]
        Description=Marathon
        After=mesos-master.service
        Requires=mesos-master.service
        [Service]
        Restart=on-failure
        EnvironmentFile=/etc/environment
        Environment=JAVA_HOME=/opt/mesosphere/dcos/latest/java
        Environment=JAVA_LIBRARY_PATH=/opt/mesosphere/dcos/latest/mesos/lib
        Environment=MESOS_NATIVE_JAVA_LIBRARY=/opt/mesosphere/dcos/latest/mesos/lib/libmesos.so
        Environment=LD_LIBRARY_PATH=/opt/mesosphere/dcos/latest/mesos/lib
        ExecStart=/opt/mesosphere/dcos/latest/java/bin/java -jar /opt/mesosphere/dcos/latest/marathon/marathon.jar --zk zk://$private_ipv4:2181/marathon --master zk://$private_ipv4:2181/mesos --hostname master${count.index}.${var.uuid}.${var.domain}
  fleet:
    metadata: role=master
CLOUD_CONFIG_MASTER
}
