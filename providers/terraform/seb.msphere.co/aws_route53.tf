resource "aws_route53_record" "mesos-master" {
  zone_id = "${var.route53_zone_id}"
  name = "master${count.index}.${var.uuid}.${var.domain}"
  type = "CNAME"
  ttl = "30"
  count = "${var.master_count}"
  records = ["${element(aws_instance.mesos-master.*.public_dns, count.index)}"]
  depends_on = ["aws_instance.mesos-master"]
}

resource "aws_route53_record" "mesos-slave" {
  zone_id = "${var.route53_zone_id}"
  name = "slave${count.index}.${var.uuid}.${var.domain}"
  type = "CNAME"
  ttl = "30"
  count = "${var.slave_count}"
  records = ["${element(aws_instance.mesos-slave.*.public_dns, count.index)}"]
  depends_on = ["aws_instance.mesos-slave"]
}
