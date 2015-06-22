#!/usr/bin/env python3
import sys
from pkgpanda.util import load_json, load_string
from pkgpanda import PackageId

from util import upload_s3


def do_upload(name, last_bootstrap):
    for id_str in load_json('packages/{}.active.json'.format(last_bootstrap)):
        id = PackageId(id_str)
        upload_s3(name, 'packages/{name}/{id}.tar.xz'.format(name=id.name, id=id_str))

    # Upload bootstrap
    upload_s3(
            name,
            'packages/{}.bootstrap.tar.xz'.format(last_bootstrap),
            'bootstrap/{}.bootstrap.tar.xz'.format(last_bootstrap),
            no_cache=True)
    upload_s3(
            name,
            'packages/{}.active.json'.format(last_bootstrap),
            'config/{}.active.json'.format(last_bootstrap),
            no_cache=True)
    upload_s3(
            name,
            'packages/bootstrap.latest',
            'bootstrap.latest',
            no_cache=True)

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("USAGE: {} testing/<name>".format(sys.argv[0]))
        sys.exit(1)
    if not sys.argv[1].startswith('testing/'):
        print("ERROR: Name must begin with 'testing'")
        sys.exit(1)

    # Get the last bootstrap build version
    last_bootstrap = load_string('packages/bootstrap.latest')

    do_upload(sys.argv[1], last_bootstrap)
