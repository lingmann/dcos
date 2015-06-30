#!/usr/bin/env python3
"""

Usage:
    cluster.py launch <name> <template_url_or_path>
    cluster.py continue <name>
    cluster.py delete <name>
"""

import boto3
import sys
import time
from docopt import docopt

cloudformation = boto3.resource('cloudformation')
s3 = boto3.resource('s3')


def do_launch(parameters):
    assert 'StackName' in parameters
    assert 'TemplateBody' in parameters or 'TemplateURL' in parameters

    stack = cloudformation.create_stack(
        DisableRollback=True,
        TimeoutInMinutes=20,
        Capabilities=['CAPABILITY_IAM'],
        Parameters=[{
            'ParameterKey': 'AcceptEULA',
            'ParameterValue': 'Yes'
        }, {
            'ParameterKey': 'KeyName',
            'ParameterValue': 'default'
        }],
        **parameters
        )
    print('StackId:', stack.stack_id)
    return stack


def wait_for_up(stack):
    shown_events = set()
    # Watch for the stack to come up. Error if steps take too long.
    print("Waiting for stack to come up")
    while(True):
        stack.reload()
        if stack.stack_status == 'CREATE_COMPLETE':
            break

        events = reversed(list(stack.events.all()))

        for event in events:
            if event.event_id in shown_events:
                continue

            shown_events.add(event.event_id)

            status = event.resource_status_reason
            if status is None:
                status = ""

            # TODO(cmaloney): Watch for Master, Slave scaling groups. When they
            # come into existence watch them for IP addresses, print the IP
            # addresses.
            # if event.logical_resource_id in ['SlaveServerGroup', 'MasterServerGroup', 'PublicSlaveServerGroup']:

            print(event.resource_status,
                  event.logical_resource_id,
                  event.resource_type,
                  status)

        time.sleep(25)

    # TODO (cmaloney): Print DnsAddress once cluster is up
    print("")
    print("")
    print("Cluster Up!")
    stack.load()  # Force the stack to update since events have happened
    for item in stack.outputs:
        if item['OutputKey'] == 'DnsAddress':
            print("DnsAddress:", item['OutputValue'])


def delete_s3_nonempty(bucket):
    # This is an exhibitor bucket, should only have one item in it. Die hard rather
    # than accidentally doing the wrong thing if there is more.

    objects = [bucket.objects.all()]
    assert len(objects) == 1

    for obj in objects:
        obj.delete()

    bucket.delete()


# Launch an AWS cluster testing that it comes up properly
def launch_cluster(parameters):
    stack = do_launch(parameters)
    wait_for_up(stack)


def resume_cluster(name):
    stack = cloudformation.Stack(name)
    wait_for_up(stack)


def delete_cluster(name):
    stack = cloudformation.Stack(name)

    # Delete the s3 bucket
    stack_resource = stack.Resource('ExhibitorS3Bucket')
    bucket = s3.Bucket(stack_resource.physical_resource_id)
    delete_s3_nonempty(bucket)

    # Delete the stack
    stack.delete()


if __name__ == "__main__":
    arguments = docopt(__doc__)

    if arguments['launch']:
        cloudformation_args = {
            'StackName': arguments['<name>']
        }
        template = arguments['<template_url_or_path>']
        if template.startswith('http://') or template.startswith('https://'):
            cloudformation_args['TemplateURL'] = template
        else:
            cloudformation_args['TemplateBody'] = open(template).read()

        launch_cluster(cloudformation_args)
        sys.exit(0)

    if arguments['continue']:
        resume_cluster(arguments['<name>'])
        sys.exit(0)

    if arguments['delete']:
        delete_cluster(arguments['<name>'])
        sys.exit(0)

    raise NotImplementedError()
