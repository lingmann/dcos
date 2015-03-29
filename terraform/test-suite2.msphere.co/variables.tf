variable "aws_region" {
  description = "The AWS region to use"
  default = "us-east-1"
}

variable "aws_access_key" {}

variable "aws_secret_key" {}

variable "github_deploy_key_base64" {}

variable "dd_api_key" {}

variable "uuid" {
  default = "test-suite2"
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
  # CoreOS 612.1.0 on PV AMI (Beta Channel)
  # HVM images not supported (requires change to initial block dev config)
  default = {
    us-east-1 = "ami-3e9cbe56"
  }
}

variable "exhibitor_s3_bucket" {
  default = "apollo-exhibitor"
}

variable "master_count" {
  default = "1"
}

variable "mesos_master_quorum" {
  default = "1"
}

variable "slave_count" {
  default = "1"
}

# Use s3.amazonaws.com to remove cloudfront cache layer
variable "bootstrap_url" {
  default = "https://s3.amazonaws.com/downloads.mesosphere.io/dcos/pkgpanda/bootstrap.tar.xz"
}
