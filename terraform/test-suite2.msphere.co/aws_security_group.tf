resource "aws_security_group" "security_group" {
  name = "${var.uuid}_sg"
  description = "${var.uuid}_sg"
  ingress {
    from_port = 22
    to_port = 22
    protocol = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  # Allow full access to SF office and VPN
  ingress {
    from_port = 0
    to_port = 65535
    protocol = "tcp"
    cidr_blocks = ["162.245.20.130/32"]
  }
  # Allow full access to SF office and VPN
  ingress {
    from_port = 0
    to_port = 65535
    protocol = "udp"
    cidr_blocks = ["162.245.20.130/32"]
  }
  ingress {
    from_port = 0
    to_port = 65535
    protocol = "tcp"
    self = true
  }
  ingress {
    from_port = 0
    to_port = 65535
    protocol = "udp"
    self = true
  }
  ingress {
    from_port = -1
    to_port = -1
    protocol = "icmp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
