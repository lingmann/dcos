#!/usr/bin/env python3
"""Library to upload package builds of DCOS

Does a full package build by default and uploads it to the requested release name.

Usage:
    upload.py <release_name> [--skip-build] [--skip-upload] [--make-latest]
"""

import botocore.client
from docopt import docopt
from functools import partial
from pkgpanda import PackageId
from pkgpanda.util import load_json, write_string
from subprocess import check_call

import util


def get_bootstrap_packages(bootstrap_id):
    return set(load_json('packages/{}.active.json'.format(bootstrap_id)))


def get_bucket():
    from aws_config import session_prod
    return session_prod.resource('s3').Bucket('downloads.mesosphere.io')


def get_object(bucket, release_name, path):
    return bucket.Object('dcos/{name}/{path}'.format(name=release_name, path=path))


def upload_s3(bucket, release_name, path, dest_path=None, args={}, no_cache=False,  if_not_exists=False):
    if no_cache:
        args['CacheControl'] = 'no-cache'

    if not dest_path:
        dest_path = path

    s3_object = get_object(bucket, release_name, dest_path)

    if if_not_exists:
        try:
            s3_object.load()
            print("Skipping {}: already exists".format(dest_path))
            return s3_object
        except botocore.client.ClientError:
            pass

    with open(path, 'rb') as data:
        print("Uploading {}{}".format(path, " as {}".format(dest_path) if dest_path else ''))
        return s3_object.put(Body=data, **args)


def upload_bootstrap(bucket, release_name, bootstrap_id):
    upload = partial(upload_s3, bucket, release_name, if_not_exists=True)
    upload('packages/{}.bootstrap.tar.xz'.format(bootstrap_id),
           'bootstrap/{}.bootstrap.tar.xz'.format(bootstrap_id))
    upload('packages/{}.active.json'.format(bootstrap_id),
           'config/{}.active.json'.format(bootstrap_id))


def upload_packages(bucket, release_name, packages=[]):
    upload = partial(upload_s3, bucket, release_name, if_not_exists=True)

    # Upload packages including config package
    for id_str in set(packages):
        pkg_id = PackageId(id_str)
        upload('packages/{name}/{id}.tar.xz'.format(name=pkg_id.name, id=id_str))


def upload_string(release_name, filename, text, s3_put_args={}):
    # Upload to s3
    bucket = get_bucket()
    obj = get_object(bucket, release_name, filename)
    obj.put(Body=text.encode('utf-8'), **s3_put_args)

    # Save as a local artifact for TeamCity
    local_path = "artifacts/" + filename
    check_call(["mkdir", "-p", local_path])
    write_string(local_path, text)

    return obj


def upload_release(release_name, bootstrap_id, extra_packages=[], bucket=None):
    if bucket is None:
        bucket = get_bucket()
    upload_packages(bucket, release_name, get_bootstrap_packages(bootstrap_id) | set(extra_packages))
    upload_bootstrap(bucket, release_name, bootstrap_id)


def do_build_and_upload(options):
    bootstrap_id = util.get_local_build(options['--skip-build'])

    if not options['--skip-upload']:
        upload_release(options['<release_name>'], bootstrap_id)

    if options['--make-latest']:
        print("Setting bootstrap.latest to id:", bootstrap_id)
        upload_string(options['<release_name>'], 'bootstrap.latest', bootstrap_id, {
            'CacheControl': 'no-cache',
            'ContentType': 'text/plain; charset=utf-8',
        })

if __name__ == '__main__':
    options = docopt(__doc__)
    do_build_and_upload(options)
