variable "aws_region" {
  description = "The AWS region to use"
  default = "us-east-1"
}

variable "aws_access_key" {}

variable "aws_secret_key" {}

variable "uuid" {
  default = "dcos-playground"
}

variable "domain" {
  default = "msphere.co"
}

variable "route53_zone_id" {
  default = "Z1UNL5ZNSHA9HU"
}

variable "aws_key_name" {
  description = "The name of the SSH keypair for the region"
  default = "default"
}

variable "aws_key_file" {}

variable "aws_instance_type" {
  default = "m3.medium"
}

variable "aws_amis" {
  # CoreOS 575.0.0 on PV AMI (Alpha Channel)
  # HVM images require a change to the initial block device configuration
  default = {
    us-east-1 = "ami-6470340c"
  }
}

variable "master_count" {
  # Currently, only a single mesos master is supported
  default = "1"
}

variable "mesos_master_quorum" {
  default = "1"
}

variable "slave_count" {
  default = "3"
}
