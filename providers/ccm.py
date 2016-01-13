#!/usr/bin/env python3
"""Utility to manage CCM VPC clusters.

Usage:
    ccm launch [options]
    ccm cluster <id> wait_for_up
    ccm cluster <id> delete
    ccm cluster <id> info
    ccm cluster <id> hosts

Options:
    --name=<name>    Prefix of cluster name to help humans [default: ccm-util]
    --time=<time>    Expiration time in minutes [default: 60]
    --count=<count>  Number of instances [default: 1]
    --type=<type>    Type of AWS EC2 instances to use [default: t2.micro]
    --os=<os>        OS to use on the instances [default: cent-os-7]
"""
import json
import sys
import time

import requests

import docopt

CCM_HOST = "https://ccm.mesosphere.com"

MAGIC_TOKEN = 'Token ji4weySp4ix5bueRb0Uj2loM9Jan3juD7Wan3yin9leeT9gEm5'


class VpcCluster():
    def __init__(self, ccm, pk):
        self.ccm = ccm
        self.pk = pk

    def hosts(self):
        self.wait_for_up()
        return json.loads(self.ccm.get_cluster_info(self.pk)["cluster_info"])["NodesIpAddresses"]

    def wait_for_up(self, timeout=300, wait=10):
        def status_cb():
            return self.ccm.get_cluster_info(self.pk)['status_text']
        tick = 0
        while status_cb() == 'Creating':
            if wait*tick > timeout:
                print("Waited over {} seconds and still no VPC!")
                return False
            time.sleep(wait)
            tick += 1
            print("Waiting for VPC to spin up ({} seconds...)".format(int(wait*tick)))
        return True

    def delete(self):
        return self.ccm.delete_cluster(self.pk)

    def get_vpc_info(self):
        return self.ccm.get_cluster_info(self.pk)

    def get_ssh_key(self):
        return self.ccm.get_ssh_key(self.pk)


class Ccm():
    def __init__(self, url=CCM_HOST):
        assert url[-1] != '/'
        assert url.startswith("https://")
        self.url = url

    def __getattr__(self, name):
        """Allows you to call wrapped HTTP methods from requests module
        """
        if name in ["get", "post", "put", "delete", "head", "options"]:
            def wrapped_request(*args, **kwargs):
                """Returns a call to requests with the ccm url and auth header
                """
                if "headers" in kwargs.keys():
                    kwargs["headers"].update({'Authorization': MAGIC_TOKEN})
                else:
                    kwargs.update({"headers": {'Authorization': MAGIC_TOKEN}})
                return getattr(requests, name)(self.url + args[0], **kwargs)
            return wrapped_request
        else:
            if name not in dir(self):
                raise NameError("Attribute not in Ccm class: {}".format(name))
            return getattr(self, name)

    def create_vpc(
            self, name, time, instance_count, instance_type, instance_os,
            key_pair_name="default", region="us-west-2"):
        """Creates VPC with AWS provider
        NOTE: Due to CCM change, use both instance_os and operating_system
        """
        parameters = {
            "name": name,
            "time": time,
            "cloud_provider": 0,
            "region": region,
            "adminlocation": "0.0.0.0/0",
            "instance_count": instance_count,
            "instance_type": instance_type,
            "instance_os": instance_os,
            "operating_system": instance_os,
            "key_pair_name": key_pair_name
            }
        response = self.post("/api/vpc/", data=parameters).json()
        try:
            cluster_id = response["id"]
        except:
            print("Could not extract ID; VPC creation failed!")
            print("Response data: {}".format(response))
            exit(1)
        return self.VpcCluster(cluster_id)

    def get_cluster_info(self, pk):
        response = self.get("/api/cluster/{}/".format(pk))
        if response.status_code == 404:
            print("Error: Info for cluster ID: {} not found!".format(pk))
            return None
        elif response.status_code == 200:
            return response.json()

    def get_all_clusters(self):
        return self.get("/api/cluster/").json()

    def get_ssh_key(self, pk):
        return self.get("/api/key/{}".format(pk)).text

    def delete_cluster(self, pk):
        return self.delete("/api/cluster/{}/".format(pk)).text

    def VpcCluster(self, pk):
        return VpcCluster(self, pk)


def main():
    try:
        arguments = docopt.docopt(__doc__)
    except docopt.DocoptExit as e:
        print(e)
        sys.exit(1)
    if arguments['launch']:
        vpc = Ccm().create_vpc(
            name=arguments['--name'],
            time=arguments['--time'],
            instance_count=arguments['--count'],
            instance_type=arguments['--type'],
            instance_os=arguments['--os']
            )
        print("VPC ID: {}".format(vpc.pk))
    if arguments['cluster']:
        cluster_id = arguments['<id>']
        cluster = VpcCluster(Ccm(), cluster_id)
        if arguments['wait_for_up']:
            cluster.wait_for_up()
        if arguments['info']:
            print(cluster.get_vpc_info())
        if arguments['delete']:
            cluster.delete()
        if arguments['hosts']:
            print(cluster.hosts())
        sys.exit(0)


if __name__ == "__main__":
    main()
