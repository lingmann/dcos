#!/usr/bin/env python3
"""DCOS release management

1. Build and upload a DCOS release to a release URL
2. Move a latest version of a release from one place to another

Co-ordinates across all providers.
"""

import argparse
import botocore.client
import copy
import importlib
import json
import os.path
import sys
from functools import partial, partialmethod
from pkgpanda import PackageId
from pkgpanda.util import load_json, write_string
from subprocess import check_call

import util

provider_names = ['aws', 'vagrant']


def to_json(data):
    return json.dumps(data, indent=2, sort_keys=True)


def get_bootstrap_packages(bootstrap_id):
    return set(load_json('packages/{}.active.json'.format(bootstrap_id)))


def get_bucket():
    from aws_config import session_prod
    return session_prod.resource('s3').Bucket('downloads.mesosphere.io')


def load_providers():
    modules = dict()
    for name in provider_names:
        modules[name] = importlib.import_module(name)
    return modules


class ChannelManager():

    def __init__(self, bucket, channel):
        self.__bucket = bucket
        self.__channel = channel

    def copy_across(self, source, bootstrap_id, active_packages):
        def do_copy(path, no_cache=None):
            print("Copying across {}".format(path))
            src_object = source.get_object(path)
            new_object = self.get_object(path)
            old_path = src_object.bucket_name + '/' + src_object.key

            if no_cache:
                new_object.copy_from(CopySource=old_path, CacheControl='no-cache')
            else:
                new_object.copy_from(CopySource=old_path)

        # Copy across all the active packages
        for id_str in active_packages:
            pkg_id = PackageId(id_str)
            do_copy('packages/{name}/{id}.tar.xz'.format(name=pkg_id.name, id=id_str))

        # Copy across the bootstrap, active.json
        do_copy('bootstrap/{}.bootstrap.tar.xz'.format(bootstrap_id))
        do_copy('bootstrap/{}.active.json'.format(bootstrap_id))

    def get_object(self, name):
        return self.__bucket.Object('dcos/{}/{}'.format(self.__channel, name))

    def read_file(self, name):
        body = self.get_object(name).get()['Body']
        data = bytes()
        for chunk in iter(lambda: body.read(4096), b''):
            data += chunk
        return data

    def upload_local_file(
            self,
            path,
            destination_path=None,
            args={},
            no_cache=False,
            if_not_exists=False):
        if no_cache:
            args['CacheControl'] = 'no-cache'

        if not destination_path:
            destination_path = path

        s3_object = self.get_object(destination_path)

        if if_not_exists:
            try:
                s3_object.load()
                print("Skipping {}: already exists".format(destination_path))
                return s3_object
            except botocore.client.ClientError:
                pass

        with open(path, 'rb') as data:
            print("Uploading {}{}".format(
                    path, " as {}".format(destination_path) if destination_path else ''))
            return s3_object.put(Body=data, **args)

    def upload_string(self, destination_path, text, args={}):
        obj = self.get_object(destination_path)
        obj.put(Body=text.encode('utf-8'), CacheControl='no-cache', **args)

        # Save a local artifact for TeamCity
        local_path = "artifacts/" + destination_path
        check_call(["mkdir", "-p", os.path.dirname(local_path)])
        write_string(local_path, text)

    def upload_bootstrap(self, bootstrap_id):
        upload = partial(self.upload_local_file, if_not_exists=True)
        upload('packages/{}.bootstrap.tar.xz'.format(bootstrap_id),
               'bootstrap/{}.bootstrap.tar.xz'.format(bootstrap_id))
        upload('packages/{}.active.json'.format(bootstrap_id),
               'bootstrap/{}.active.json'.format(bootstrap_id))

    def upload_packages(self, packages):
        for id_str in set(packages):
            pkg_id = PackageId(id_str)
            self.upload_local_file(
                'packages/{name}/{id}.tar.xz'.format(name=pkg_id.name, id=id_str),
                if_not_exists=True)

    def upload_provider_packages(self, provider_data):
        extra_packages = list()
        for data in provider_data.values():
            extra_packages += data['extra_packages']
        self.upload_packages(extra_packages)

    def upload_provider_files(self, provider_data, path_key, prefix):
        for provider_name, data in provider_data.items():
            for file_info in data['files']:
                if path_key not in file_info:
                    continue

                paths = file_info[path_key]

                # Avoid accidentally iterating strings by letter.
                # providers may give a single path or a list of paths.
                if isinstance(paths, str):
                    paths = [paths]

                for path in paths:
                    if prefix:
                        path = provider_name + '/' + path

                    if 'upload_args' in file_info:
                        self.upload_string(
                            path,
                            file_info['content'],
                            args=file_info['upload_args'])
                    else:
                        self.put_text(path, file_info['content'])

    def upload_providers_and_activate(self, bootstrap_id, commit, metadata_json, provider_data):
        # Upload provider artifacts to their stable locations
        print("Uploading stable artifacts")
        self.upload_provider_packages(provider_data)
        self.put_json("metadata/{}.json".format(commit), metadata_json)
        self.upload_provider_files(provider_data, 'stable_path', prefix=True)

        # Make active point to all the arifacts
        # - bootstrap.latest
        # - metadata.latest.json
        # - provider templates to known_paths
        print("Marking new build as the latest")
        self.put_text('bootstrap.latest', bootstrap_id)
        self.put_json('metadata.json', metadata_json)
        self.upload_provider_files(provider_data, 'known_path', prefix=False)

    @property
    def repository_url(self):
        return 'https://downloads.mesosphere.com/dcos/{}'.format(self.__channel)

    put_text = partialmethod(upload_string, args={'ContentType': 'text/plain; charset=utf-8'})
    put_json = partialmethod(upload_string, args={'ContentType': 'application/json'})


# Generate provider templates against the bootstrap id, capturing the
# needed packages.
# {
#   <provider_name>: {
#     'extra_packages': [],
#     'files': [{
#        # NOTE: May specify a list of known_names
#       'known_path': 'cloudformation/single-master.cloudformation.json',
#       'stable_path': 'cloudformation/{}.cloudformation.json'
#       'content': ''
#       }]}}
def get_provider_data(repository_url, bootstrap_id, tag, channel_name, commit):
    provider_data = {}
    providers = load_providers()
    for name, module in providers.items():
        # Use keyword args to make not matching ordering a loud error around changes.
        provider_data[name] = module.do_create(
            tag=tag,
            channel=channel_name,
            commit=commit,
            gen_arguments=copy.deepcopy({
                'bootstrap_id': bootstrap_id,
                'channel_name': tag,
                'bootstrap_url': repository_url
            }))

    cleaned = copy.deepcopy(provider_data)
    for data in cleaned.values():
        for file_info in data['files']:
            file_info.pop('content')
            file_info.pop('upload_args', None)

    return provider_data, cleaned


def do_promote(options):
    print("Promoting channel {} to {}".format(options.source_channel, options.destination_channel))
    bucket = get_bucket()
    destination = ChannelManager(bucket, options.destination_channel)
    source = ChannelManager(bucket, options.source_channel)

    # Download source channel metadata
    metadata = json.loads(source.read_file('metadata.json').decode('utf-8'))
    bootstrap_id = metadata['bootstrap_id']
    active_package = metadata['active_package']
    commit = metadata['commit']

    if util.dcos_image_commit != metadata['commit']:
        print("WARNING: Running newer release script against different release.")

    print("version tag:", metadata['tag'])

    # Run providers against repository_url for destination channel
    print("Running providers to generate new provider config")
    provider_data, cleaned_provider_data = get_provider_data(
        destination.repository_url,
        bootstrap_id,
        metadata['tag'],
        options.destination_channel,
        metadata['commit']
        )

    metadata_json = to_json({
            'active_package': active_package,
            'bootstrap_id': bootstrap_id,
            'commit': commit,
            'date': util.template_generation_date,
            'provider_data': cleaned_provider_data,
            'tag': metadata['tag']
        })

    # Copy across packages, bootstrap.
    destination.copy_across(source, bootstrap_id, active_package)

    # Upload provider artifacts, mark as active
    destination.upload_providers_and_activate(bootstrap_id, commit, metadata_json, provider_data)
    print("Channel {} now at tag {}".format(options.destination_channel, metadata['tag']))


def do_create(options):
    channel_name = 'testing/' + options.destination_channel
    channel = ChannelManager(get_bucket(), channel_name)
    commit = util.dcos_image_commit
    print("Creating release on channel:", channel_name)
    print("version tag:", options.tag)

    # Build packages and generate bootstrap
    print("Building packages")
    bootstrap_id = util.get_local_build(options.skip_build)
    provider_data, cleaned_provider_data = get_provider_data(
        channel.repository_url,
        bootstrap_id,
        options.tag,
        channel_name,
        commit)

    metadata_json = to_json({
            'active_package': list(get_bootstrap_packages(bootstrap_id)),
            'bootstrap_id': bootstrap_id,
            'commit': commit,
            'date': util.template_generation_date,
            'provider_data': cleaned_provider_data,
            'tag': options.tag
        })

    # Upload packages, bootstrap.
    print("Uploading packages")
    if options.skip_upload:
        return
    channel.upload_packages(get_bootstrap_packages(bootstrap_id))
    channel.upload_bootstrap(bootstrap_id)

    # Upload provider artifacts, mark as active
    channel.upload_providers_and_activate(bootstrap_id, commit, metadata_json, provider_data)
    print("New release created on channel", channel_name)


def main():
    parser = argparse.ArgumentParser(description='DCOS Release Management Tool.')
    subparsers = parser.add_subparsers(title='commands')

    # Moves the latest of a given release name to the given release name.
    promote = subparsers.add_parser('promote')
    promote.set_defaults(func=do_promote)
    promote.add_argument('source_channel')
    promote.add_argument('destination_channel')

    # Creates, uploads, and marks as latest.
    # The marking as latest is ideally atomic (At least all artifacts when they
    # are uploaded should never result in a state where things don't work).
    create = subparsers.add_parser('create')
    create.set_defaults(func=do_create)
    create.add_argument('destination_channel')
    create.add_argument('tag')
    create.add_argument('--skip-upload', action='store_true')
    create.add_argument('--skip-build', action='store_true')

    # Parse the arguments and dispatch.
    options = parser.parse_args()
    if hasattr(options, 'func'):
        options.func(options)
        sys.exit(0)
    else:
        parser.print_help()
        print("ERROR: Must use a subcommand")
        sys.exit(1)


if __name__ == '__main__':
    main()
