#!/usr/bin/env python3
import botocore.exceptions
import boto3

cloudformation = boto3.resource('cloudformation')
s3 = boto3.resource('s3')


def delete_s3_nonempty(bucket):
    # This is an exhibitor bucket, should only have one item in it. Die hard rather
    # than accidentally doing the wrong thing if there is more.

    objects = [bucket.objects.all()]
    assert len(objects) == 1

    for obj in objects:
        obj.delete()

    bucket.delete()


def delete_buckets_without_stacks():
    deleted = 0
    skipped = 0
    exception = 0

    stack_bucket_names = set()
    # Find s3 buckets by stack
    for stack in cloudformation.stacks.all():
        stack_bucket_names.add(stack.Resource('ExhibitorS3Bucket').physical_resource_id)

    for bucket in s3.buckets.all():
        if bucket.name in stack_bucket_names:
            skipped += 1
            print("Skipping bucket {}, in use".format(bucket.name))
            continue
        try:
            delete_s3_nonempty(bucket)
            deleted += 1
            print("DELETE bucket {}".format(bucket.name))
        except botocore.exceptions.ClientError as ex:
            print("EXCEPTION: on bucket {}: ".format(bucket.name), ex)
            exception += 1

    print("deleted: {} kept: {} exception: {}".format(deleted, skipped, exception))

if __name__ == '__main__':
    delete_buckets_without_stacks()
