#!/usr/bin/env python3

import json
import subprocess

regions = ['us-east-1', 'us-west-2', 'us-west-1', 'eu-west-1', 'eu-central-1', 'ap-southeast-1', 'ap-southeast-2', 'ap-northeast-1', 'sa-east-1']


def get_ami_for_region(region):
    return subprocess.Popen(['aws', 'ec2', 'describe-images', '--region', region, '--filters', 'Name=name,Values=amzn-ami-vpc-nat-hvm-2014.03.2.x86_64-ebs'], stdout=subprocess.PIPE).communicate()[0]



if __name__ == '__main__':
    region_to_ami = {}
    for region in regions:
        json_data = json.loads(get_ami_for_region(region).decode("utf-8"))

        ami_id = json_data['Images'][0]['ImageId']

        region_to_ami[region] = { 'default' : ami_id }
    print(json.dumps(region_to_ami, indent=2, sort_keys=True, separators=(', ', ': ')))
