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
  # Using YAML anchors and aliases to parameterize cloud-config
  # See: https://github.com/hashicorp/terraform/issues/642
  user_data = <<CLOUD_CONFIG_MASTER
#cloud-config

dynamic:
  discovery_url: &DISCOVERY_YAML
    discovery: ${var.discovery_url}
  cloudenv: &CLOUDENV_CONTENT_YAML
    content: |
      AWS_REGION=${var.aws_region}
      AWS_ACCESS_KEY_ID=${var.aws_access_key}
      AWS_SECRET_ACCESS_KEY=${var.aws_secret_key}
      EC2_PUBLIC_HOSTNAME=master${count.index}.${var.uuid}.${var.domain}
  mesos_master: &MESOS_MASTER_CONTENT_YAML
    content: |
      MESOS_LOG_DIR=/var/log/mesos
      MESOS_WORK_DIR=/var/lib/mesos/master
      MESOS_ZK=zk://127.0.0.1:2181/mesos
      MESOS_QUORUM=${var.mesos_master_quorum}
  zookeeper: &ZOOKEEPER_CONTENT_YAML
    content: |
      S3_BUCKET=apollo-exhibitor
      S3_PREFIX=dcos-${var.uuid}
      EXHIBITOR_WEB_UI_PORT=8181

${file("cloud-config-master.yml")}
CLOUD_CONFIG_MASTER
}
