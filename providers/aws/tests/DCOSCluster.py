#!/usr/bin/python
import json
import uuid

from boto import cloudformation
from boto import ec2
from boto.s3.connection import S3Connection
from boto.ec2 import elb
from boto.exception import BotoServerError


class DCOSCluster(object):
    def __init__(self, region, aws_access_key_id, aws_secret_key, **params):
        self.region = region
        self.id = params.get('stack_name') or self._generate_stack_id
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_key = aws_secret_key
        self.template = json.dumps(
            json.load(open('simple.cloudformation.json')))

        self.params = list(params.get('params').iteritems())

        self._cf_connection = self._create_connection()

    def _create_connection(self):
        return cloudformation.connect_to_region(
            self.region,
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_key)

    def _generate_stack_id(self):
        return "dcos-cluster-%s" % (uuid.uuid4().hex)

    def _update_parameters(self):
        pass

    def create(self):
        self._cf_connection.create_stack(
                self.id,
                template_body=self.template,
                parameters=self.params,
                capabilities=['CAPABILITY_IAM'])

    def delete(self):
        exhibitor_s3_bucket = self.describe()['exhibitor_s3_bucket']
        AWSUtils.deleteNonEmptyS3Bucket(
            exhibitor_s3_bucket,
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_key=self.aws_secret_key)

        self._cf_connection.delete_stack(self.id)

    def describe(self):
        resources = self._get_resources()
        elb_physical_id = [resource['physical_resource_id'] for resource in resources if resource['logical_resource_id'] == "ElasticLoadBalancer"]
        elb_physical_id = elb_physical_id[0]

        master_sg = [resource['physical_resource_id'] for resource in resources if resource['logical_resource_id'] == "MasterSecurityGroup"]
        master_sg = master_sg[0]

        exhibitor_s3_bucket = [resource['physical_resource_id'] for resource in resources if resource['logical_resource_id'] == "ExhibitorS3Bucket"]
        exhibitor_s3_bucket = exhibitor_s3_bucket[0]

        try:
            elb_dns_name = AWSUtils.lookupLoadbalancerDNS(lb_name=elb_physical_id,
                                                      aws_access_key_id=self.aws_access_key_id,
                                                      aws_secret_key=self.aws_secret_key,
                                                      region=self.region)

            elb_instances = AWSUtils.lookupLoadbalancerInstanceDNS(lb_name=elb_physical_id,
                                                      aws_access_key_id=self.aws_access_key_id,
                                                      aws_secret_key=self.aws_secret_key,
                                                      region=self.region)
        except BotoServerError as e:
            elb_dns_name = ""
            elb_instances = []

        return {"elb_dns_name": elb_dns_name,
                "exhibitor_s3_bucket": exhibitor_s3_bucket,
                "masters_dns_names": elb_instances,
                "master_sg": master_sg}

    def get_events(self):
        c = self._create_connection()
        stacks = c.describe_stacks(stack_name_or_id=self.id)
        assert len(stacks) == 1
        return [{"event_id": event.event_id,
                 "resource_type": event.resource_type,
                 "timestamp": event.timestamp.strftime('%s'),
                 "resource_status": event.resource_status} for event in stacks[0].describe_events()]

    def _get_resources(self):
        c = self._create_connection()
        stacks = c.describe_stacks(stack_name_or_id=self.id)
        assert len(stacks) == 1
        resources = stacks[0].list_resources()
        return [{"resource_type": resource.resource_type,
                 "physical_resource_id": resource.physical_resource_id,
                 "logical_resource_id": resource.logical_resource_id} for resource in resources]

    def status(self):
        stacks = self._cf_connection.describe_stacks(stack_name_or_id=self.id)
        assert len(stacks) == 1
        return stacks[0].stack_status

    @property
    def uri(self):
        return "http://%s" % (self.describe()['elb_dns_name'])

    @property
    def dns_name(self):
        return self.describe()['elb_dns_name']


class AWSUtils(object):
    @staticmethod
    def lookupLoadbalancerDNS(lb_name, aws_access_key_id, aws_secret_key, region):
        c = elb.connect_to_region(region, aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_key)
        elbs = c.get_all_load_balancers(load_balancer_names=[lb_name])
        return elbs[0].dns_name

    @staticmethod
    def lookupLoadbalancerInstanceDNS(lb_name, aws_access_key_id, aws_secret_key, region):
        c = elb.connect_to_region(region, aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_key)
        ec2_connection = ec2.connect_to_region(region, aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_key)
        elbs = c.get_all_load_balancers(load_balancer_names=[lb_name])

        load_balancer = elbs[0]
        instance_ids = [ instance.id for instance in load_balancer.instances ]
        reservations = ec2_connection.get_all_instances(instance_ids)
        instance_addresses = [ i.public_dns_name for r in reservations for i in r.instances ]
        return instance_addresses

    @staticmethod
    def deleteNonEmptyS3Bucket(bucket_name, aws_access_key_id, aws_secret_key):
        c = S3Connection(aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_key)
        bucket = c.get_bucket(bucket_name)

        for key in bucket.list():
            key.delete()

        c.delete_bucket(bucket_name)
