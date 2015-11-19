#!/usr/bin/env python3
"""DCOS release management

1. Build and upload a DCOS release to a release URL
2. Move a latest version of a release from one place to another

Co-ordinates across all providers.
"""

import abc
import azure.storage
import azure.storage.blob
import argparse
import botocore.client
import copy
import importlib
import json
import mimetypes
import os.path
import subprocess
import sys
import tempfile
from functools import partial, partialmethod

import pkgpanda
import pkgpanda.build
import pkgpanda.util
import aws_config
import util

provider_names = ['aws', 'azure', 'vagrant']

AZURE_TESTING_CONTAINER = 'dcos'
METADATA_FILE = 'metadata.json'


def to_json(data):
    return json.dumps(data, indent=2, sort_keys=True)


def get_bootstrap_packages(bootstrap_id):
    return set(pkgpanda.util.load_json('packages/{}.active.json'.format(bootstrap_id)))


def load_providers():
    modules = dict()
    for name in provider_names:
        modules[name] = importlib.import_module("providers." + name)
    return modules


class CopyAcrossException(Exception):
    """A Custom Exception raise when trying to copy across providers and either source of
       destination provider is missing"""


class AbstractStorageProvider(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def copy_across(self):
        pass

    @abc.abstractmethod
    def upload_local_file(self):
        pass

    @abc.abstractmethod
    def upload_string(self):
        pass

    def upload_packages(self, packages):
        for id_str in set(packages):
            pkg_id = pkgpanda.PackageId(id_str)
            self.upload_local_file(
                'packages/{name}/{id}.tar.xz'.format(name=pkg_id.name, id=id_str),
                if_not_exists=True)

    def upload_bootstrap(self, bootstrap_dict):
        upload = partial(self.upload_local_file, if_not_exists=True)
        for bootstrap_id in bootstrap_dict.values():
            upload('packages/{}.bootstrap.tar.xz'.format(bootstrap_id),
                   'bootstrap/{}.bootstrap.tar.xz'.format(bootstrap_id))
            upload('packages/{}.active.json'.format(bootstrap_id),
                   'bootstrap/{}.active.json'.format(bootstrap_id))

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

    def upload_provider_packages(self, provider_data):
        extra_packages = list()
        for data in provider_data.values():
            extra_packages += data['extra_packages']
        self.upload_packages(extra_packages)

    def upload_providers_and_activate(self, bootstrap_dict, commit, metadata_json, provider_data):
        # Upload provider artifacts to their stable locations
        print("Uploading stable artifacts to Azure Blob storage")
        self.upload_provider_packages(provider_data)
        self.put_json("metadata/{}.json".format(commit), metadata_json)
        self.upload_provider_files(provider_data, 'stable_path', prefix=True)

        # Make active point to all the arifacts
        # - bootstrap.latest
        # - metadata.latest.json
        # - provider templates to known_paths
        # - dcos_generate_config.sh
        print("Marking new build as the latest")
        self.put_text('bootstrap.latest', bootstrap_dict[None])
        for variant, bootstrap_id in bootstrap_dict.items():
            if variant is None:
                continue
            self.put_text(variant + '.bootstrap.latest', bootstrap_id)

        self.put_json(METADATA_FILE, metadata_json)
        self.upload_provider_files(provider_data, 'known_path', prefix=False)
        # TODO(cmaloney): Make a stable location version of this like
        # provider_files does. Not extending provider_files currently because
        # those are all in-memory, and this one is a couple hundred MB of data.
        # TODO(cmaloney): Make at a reliable name so caching can be enabled.
        self.upload_local_file('dcos_generate_config.sh', no_cache=True)

    def _copy_across(self, bootstrap_dict, active_packages, do_copy):
        # Copy across all the active packages
        for id_str in active_packages:
            pkg_id = pkgpanda.PackageId(id_str)
            do_copy('packages/{name}/{id}.tar.xz'.format(name=pkg_id.name, id=id_str))

        # Copy across the bootstrap, active.json
        for bootstrap_id in bootstrap_dict.values():
            do_copy('bootstrap/{}.bootstrap.tar.xz'.format(bootstrap_id))
            do_copy('bootstrap/{}.active.json'.format(bootstrap_id))


class AzureStorageProvider(AbstractStorageProvider):
    name = 'azure'

    def __init__(self, channel):
        self.__channel = channel
        account_name = os.environ.get('AZURE_STORAGE_ACCOUNT')
        account_key = os.environ.get('AZURE_STORAGE_ACCESS_KEY')
        self.blob_service = azure.storage.blob.BlobService(account_name=account_name, account_key=account_key)

    @property
    def repository_url(self):
        return 'http://mesospheredownloads.blob.core.windows.net/dcos/{}'.format(self.__channel)

    def upload_local_file(self, path, destination_path=None, container=None, args={}, no_cache=False,
                          if_not_exists=False):
        if not destination_path:
            destination_path = path

        destination_path = os.path.join(self.__channel, destination_path.lstrip('/'))
        if not container:
            container = AZURE_TESTING_CONTAINER

        if no_cache:
            args['cache_control'] = None

        if if_not_exists:
            try:
                self.blob_service.get_blob_properties(container, destination_path)
                print("Skipping {}: already exists".format(destination_path))
                return
            except azure.storage._common_error.AzureMissingResourceHttpError:
                pass

        print("Uploading {}{}".format(path, " as {}".format(destination_path) if destination_path else ''))
        self.blob_service.put_block_blob_from_path(
            container,
            destination_path,
            path,
            x_ms_blob_content_type=mimetypes.guess_type(path),
            **args)

    def upload_packages(self, packages):
        super().upload_packages(packages)

    def upload_bootstrap(self, bootstrap_dict):
        super().upload_bootstrap(bootstrap_dict)

    def copy_across(self, source, bootstrap_dict, active_packages):
        def do_copy(path, no_cache=None):
            print("Copying across {}".format(path))
            self.blob_service.copy_blob(AZURE_TESTING_CONTAINER,
                                        os.path.join(self.__channel, path.lstrip('/')),
                                        os.path.join(source.repository_url, path.lstrip('/')))

        super()._copy_across(bootstrap_dict, active_packages, do_copy)

    def upload_provider_files(self, provider_data, path_key, prefix):
        super().upload_provider_files(provider_data, path_key, prefix)

    def upload_provider_packages(self, provider_data):
        super().upload_provider_packages(provider_data)

    def upload_providers_and_activate(self, bootstrap_dict, commit, metadata_json, provider_data):
        super().upload_providers_and_activate(bootstrap_dict, commit, metadata_json, provider_data)

    def upload_string(self, destination_path, text, args, container=None):
        destination_path = os.path.join(self.__channel, destination_path.lstrip('/'))
        if 'ContentType' in args:
            content_type_value = args['ContentType']
            del args['ContentType']
            args.update({'x_ms_blob_content_type': content_type_value})
        if not container:
            container = AZURE_TESTING_CONTAINER
        self.blob_service.put_block_blob_from_text(container, destination_path, text.encode('utf-8'), **args)

    put_text = partialmethod(upload_string, args={'x_ms_blob_content_type': 'text/plain; charset=utf-8'})

    put_json = partialmethod(upload_string, args={'x_ms_blob_content_type': 'application/json'})


class S3StorageProvider(AbstractStorageProvider):
    name = 'aws'

    def __init__(self, channel):
        self.__channel = channel
        self.__bucket = aws_config.session_prod.resource('s3').Bucket('downloads.mesosphere.io')

    @property
    def repository_url(self):
        return 'https://downloads.mesosphere.com/dcos/{}'.format(self.__channel)

    def copy_across(self, source, bootstrap_dict, active_packages):
        def do_copy(path, no_cache=None):
            print("Copying across {}".format(path))
            src_object = source.get_object(path)
            new_object = self.get_object(path)
            old_path = src_object.bucket_name + '/' + src_object.key

            if no_cache:
                new_object.copy_from(CopySource=old_path, CacheControl='no-cache')
            else:
                new_object.copy_from(CopySource=old_path)
        super()._copy_across(bootstrap_dict, active_packages, do_copy)

    def get_object(self, name):
        return self.__bucket.Object('dcos/{}/{}'.format(self.__channel, name))

    def read_file(self, name):
        body = self.get_object(name).get()['Body']
        data = bytes()
        for chunk in iter(lambda: body.read(4096), b''):
            data += chunk
        return data

    def download_if_not_exist(self, name, output_filename):
        if not os.path.exists(output_filename):
            return self.get_object(name).download_file(output_filename)

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
            print("Uploading {}/{}".format(
                path, " as {}".format(destination_path) if destination_path else ''))
            return s3_object.put(Body=data, **args)

    def upload_string(self, destination_path, text, args={}):
        obj = self.get_object(destination_path)
        obj.put(Body=text.encode('utf-8'), CacheControl='no-cache', **args)

        # Save a local artifact for TeamCity
        local_path = "artifacts/" + destination_path
        subprocess.check_call(["mkdir", "-p", os.path.dirname(local_path)])
        pkgpanda.util.write_string(local_path, text)

    def upload_bootstrap(self, bootstrap_dict):
        super().upload_bootstrap(bootstrap_dict)

    def upload_packages(self, packages):
        super().upload_packages(packages)

    def upload_provider_packages(self, provider_data):
        super().upload_provider_packages(provider_data)

    def upload_provider_files(self, provider_data, path_key, prefix):
        super().upload_provider_files(provider_data, path_key, prefix)

    def upload_providers_and_activate(self, bootstrap_dict, commit, metadata_json, provider_data):
        super().upload_providers_and_activate(bootstrap_dict, commit, metadata_json, provider_data)

    put_text = partialmethod(upload_string, args={'ContentType': 'text/plain; charset=utf-8'})

    put_json = partialmethod(upload_string, args={'ContentType': 'application/json'})


class ChannelManager():
    """
    Magic Proxy class wil accept a lit of storage providers, iterate over the list and call a function against
    each storage provider.

    channel = ChannelManager([S3StorageProvider('s3provider_name'), AzureStorageProvider('azure_provider_name')])
    channel.call_me() -> S3StorageProvider('s3provider_name').call_me and
    AzureStorageProvider('azure_provider_name').call_me()
    """
    def __init__(self, storage_providers):
        self.__storage_providers = storage_providers

        # A default storage provider is the very first element in self.__sotrage_providers
        self.__default_storage_provider = storage_providers[0]

    def __getattr__(self, name, *args, **kwargs):
        def wrapper(*args, **kwargs):
            for provider in self.__storage_providers:
                if hasattr(provider, name):
                    getattr(provider, name)(*args, **kwargs)
                else:
                    raise AttributeError('Provider {} does not have attribute {}'.format(provider.name, name))
        return wrapper

    def copy_across(self, source, bootstrap_dict, active_packages):
        """
        Dispatch copy_across in a special way. source and destination will both have self.__storage_providers
        as an array of different storage providers This function will match providers by their type
        """
        copy_providers = {}
        for destination_provider in self.__storage_providers:
            found_source_provider = False
            for source_provider in source.__storage_providers:
                if destination_provider.name == source_provider.name:
                    found_source_provider = True
                    copy_providers.update({
                        destination_provider.name: (source_provider, destination_provider)})
            if not found_source_provider:
                raise CopyAcrossException(
                    'Cannot promote for {}, source provider not found'.format(destination_provider.name))
            for provider_name, providers in copy_providers.items():
                source_provider, destination_provider = providers
                destination_provider.copy_across(source_provider, bootstrap_dict, active_packages)

    @property
    def repository_url(self):

        repository_urls = {}
        for provider in self.__storage_providers:
            repository_urls.update({provider.name: provider.repository_url})
        repository_urls.update({'default': self.__default_storage_provider.repository_url})
        return repository_urls

    def read_file(self, name):
        for provider in self.__storage_providers:
            if provider.name == 'aws':
                return provider.read_file(name)


def all_storage_providers(channel):
    """
    Return a list of all StorageProviders initialized with the channel name.
    """
    return [S3StorageProvider(channel), AzureStorageProvider(channel)]


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
    bootstrap_url = repository_url['default']
    for name, module in providers.items():
        if name in repository_url:
            bootstrap_url = repository_url[name]

        # Use keyword args to make not matching ordering a loud error around changes.
        provider_data[name] = module.do_create(
            tag=tag,
            channel=channel_name,
            commit=commit,
            gen_arguments=copy.deepcopy({
                'bootstrap_id': bootstrap_id,
                'channel_name': tag,
                'bootstrap_url': bootstrap_url
            }))

    cleaned = copy.deepcopy(provider_data)
    for data in cleaned.values():
        for file_info in data['files']:
            file_info.pop('content')
            file_info.pop('upload_args', None)

    return provider_data, cleaned


def do_promote(options):
    print("Promoting channel {} to {}".format(options.source_channel, options.destination_channel))
    destination_storage_providers = all_storage_providers(options.destination_channel)
    source_storage_providers = all_storage_providers(options.source_channel)
    destination = ChannelManager(destination_storage_providers)
    source = ChannelManager(source_storage_providers)

    # Download source channel metadata
    metadata = json.loads(source.read_file(METADATA_FILE).decode('utf-8'))
    bootstrap_dict = metadata['bootstrap_dict']

    # None gets stored as null in the key of the dictionary. Undo that.
    default_bootstrap_id = bootstrap_dict['null']
    del bootstrap_dict['null']
    bootstrap_dict[None] = default_bootstrap_id

    active_packages = metadata['active_packages']
    commit = metadata['commit']

    if util.dcos_image_commit != metadata['commit']:
        print("WARNING: Running newer release script against different release.")

    print("version tag:", metadata['tag'])

    # TODO(cmaloney): Run against all bootstrap variants / allow providers to
    # make multiple variants for the multiple variants of DCOS available.
    # Run providers against repository_url for destination channel
    print("Running providers to generate new provider config")
    provider_data, cleaned_provider_data = get_provider_data(
        destination.repository_url,
        default_bootstrap_id,
        metadata['tag'],
        options.destination_channel,
        metadata['commit'])

    # TODO(cmaloney): Extract building genconf, checking these variables to a function.
    # Download the bootstrap if it doesn't exist
    bootstrap_path = '/{}.bootstrap.tar.xz'.format(default_bootstrap_id)
    source.download_if_not_exist('bootstrap' + bootstrap_path, 'packages' + bootstrap_path)

    # Check needed configuration is set
    pkgpanda_src = do_variable_set_or_exists('PKGPANDA_SRC', 'ext/pkgpanda')
    dcos_image_src = do_variable_set_or_exists('DCOS_IMAGE_SRC', os.getcwd())

    print("Building dcos-genconf docker container")
    genconf_metadata = make_genconf_docker(
        pkgpanda_src,
        dcos_image_src,
        options.destination_channel,
        default_bootstrap_id)

    metadata_json = to_json(
        {
            'active_packages': active_packages,
            'bootstrap_dict': bootstrap_dict,
            'commit': commit,
            'date': util.template_generation_date,
            'provider_data': cleaned_provider_data,
            'tag': metadata['tag'],
            'genconf_docker_tag': open('docker-tag').read()})

    # Copy across packages, bootstrap.
    destination.copy_across(source, bootstrap_dict, active_packages)

    # TODO(cmaloney): Allow pushing multiple dcos-genconf docker, one for each bootstrap variant.
    # TODO(cmaloney): push the genconf docker into upload_providers_and_activate. Also copy the image
    # to have the channel name as a tag.
    print("Pushing dcos-genconf docker container")
    push_genconf_docker(genconf_metadata)

    # Upload provider artifacts, mark as active
    destination.upload_providers_and_activate(bootstrap_dict, commit, metadata_json, provider_data)
    print("Channel {} now at tag {}".format(options.destination_channel, metadata['tag']))


def get_local_build(skip_build, repository_url, storage_provider=None):
    if not storage_provider:
        storage_provider = 'aws'

    if not skip_build:
        subprocess.check_call(
            ['mkpanda', 'tree', '--mkbootstrap', '--repository-url=' + repository_url[storage_provider]],
            cwd='packages',
            env=os.environ)

    return pkgpanda.build.get_last_bootstrap_set('packages')


def do_build_packages(repository_url, skip_build):
    dockerfile = 'docker/builder/Dockerfile'
    container_name = 'mesosphere/dcos-builder:dockerfile-' + pkgpanda.build.sha1(dockerfile)
    print("Attempting to pull dcos-builder docker:", container_name)
    pulled = False
    try:
        subprocess.check_call(['docker', 'pull', container_name])
        pulled = True
        # TODO(cmaloney): Differentiate different failures of running the process better here
    except subprocess.CalledProcessError:
        pulled = False

    if not pulled:
        print("Pull failed, building instead:", container_name)
        # Pull failed, build it
        subprocess.check_call(
            ['docker', 'build', '-t', container_name, '-'],
            stdin=open("docker/builder/Dockerfile"))

        # TODO(cmaloney): Push the built docker image on successful package build to both
        # 1) commit-<commit_id>
        # 2) Dockerfile-<file_contents_sha1>
        # 3) bootstrap-<bootstrap_id>
        # So we can track back the builder id for a given commit or bootstrap id, and reproduce whatever
        # we need. The  Dockerfile-<sha1> is useful for making sure we don't rebuild more than
        # necessary.
        subprocess.check_call(['docker', 'push', container_name])

    # mark as latest so it will be used when building packages
    subprocess.check_call(['docker', 'tag', '-f', container_name, 'dcos-builder:latest'])

    bootstrap_dict = get_local_build(skip_build, repository_url)

    return bootstrap_dict


def do_variable_set_or_exists(env_var, path):
    # Get out the environment variable if needed
    path = os.environ.get(env_var, default=path)

    # If we're all set exit
    if os.path.exists(path):
        return path

    # Error appropriately
    if path in os.environ:
        print("ERROR: {} set in environment doesn't point to a directory that exists '{}'".format(env_var, path))
    else:
        print(
            ("ERROR: Default directory for {var} doens't exist. Set {var} in the environment " +
             "or ensure there is a checkout at the default path {path}.").format(
                var=env_var,
                path=path
                ))
    sys.exit(1)


def check_genconf_prereqs(pkgpanda_src, dcos_image_src, bootstrap_id):
    def check_is_git_repo(path, identifier):
        assert(path[-1] != '/')

        if not os.path.exists(path + '/.git'):
            raise ValueError(
                identifier + "_src must be a git repository containing a .git " +
                "folder. Given directory " + path + " isn't.")

        sha1 = subprocess.check_output(['git', '-C', path, 'rev-parse', 'HEAD']).decode('utf-8')
        assert len(sha1) > 0

        return sha1

    pkgpanda_sha1 = check_is_git_repo(pkgpanda_src, 'pkgpanda')
    dcos_image_sha1 = check_is_git_repo(dcos_image_src, 'dcos_image')

    docker_tag = dcos_image_sha1[:12] + '-' + pkgpanda_sha1[:12] + '-' + bootstrap_id[:12]
    genconf_tar = "dcos-genconf." + docker_tag + ".tar"
    bootstrap_filename = bootstrap_id + ".bootstrap.tar.xz"
    bootstrap_path = os.getcwd() + "/packages/" + bootstrap_filename

    return {
        'pkgpanda_src': pkgpanda_src,
        'dcos_image_src': dcos_image_src,
        'bootstrap_id': bootstrap_id,
        'docker_tag': docker_tag,
        'genconf_tar': genconf_tar,
        'bootstrap_filename': bootstrap_filename,
        'bootstrap_path': bootstrap_path,
        'docker_image_name': 'mesosphere/dcos-genconf:' + docker_tag
    }


def make_build_dir(metadata):
    tmp_dir = tempfile.TemporaryDirectory()
    assert tmp_dir.name[-1] != '/'
    subprocess.check_call([
        'mkdir',
        '-p',
        tmp_dir.name + '/pkgpanda',
        tmp_dir.name + '/dccos-image',
        tmp_dir.name + '/bootstrap'])

    # clone the repository dropping git history other than last commit so that it
    # is still a valid git checkout but we lose any local modifications, and don't
    # capture any temporary files in the filesystem (package builds, etc).
    subprocess.check_call([
        'git',
        'clone',
        '--depth=1',
        'file://' + metadata['pkgpanda_src'],
        tmp_dir.name + '/pkgpanda'])

    subprocess.check_call([
        'git',
        'clone',
        '--depth=1',
        'file://' + metadata['dcos_image_src'],
        tmp_dir.name + '/dcos-image'])

    pkgpanda.util.write_string(
        tmp_dir.name + '/Dockerfile',
        pkgpanda.util.load_string('docker/genconf/Dockerfile.template').format(**metadata))

    pkgpanda.util.write_string(
        'dcos_generate_config.sh',
        pkgpanda.util.load_string('docker/genconf/dcos_generate_config.sh.in').format(**metadata) + '\n#EOF#\n')

    return tmp_dir


def make_genconf_docker(pkgpanda_src, dcos_image_src, channel_name, bootstrap_id):
    assert len(channel_name) > 0
    assert len(bootstrap_id) > 0

    metadata = check_genconf_prereqs(pkgpanda_src, dcos_image_src, bootstrap_id)
    metadata['channel_name'] = channel_name

    with make_build_dir(metadata) as build_dir:
        print("Pulling base docker")
        subprocess.check_call(['docker', 'pull', 'python:3.4.3-slim'])

        print("Building docker container in " + build_dir)
        build_bootstrap_path = build_dir + '/' + metadata['bootstrap_filename']
        subprocess.check_call(['cp', metadata['bootstrap_path'], build_bootstrap_path])
        subprocess.check_call(['docker', 'build', '-t', metadata['docker_image_name'], build_dir])
        # Clean up the giant bootstrap to save space
        subprocess.check_call(['rm', build_bootstrap_path])
        pkgpanda.util.write_string('docker-tag', metadata['docker_tag'])
        pkgpanda.util.write_string('docker-tag.txt', metadata['docker_tag'])

        print("Building dcos_generate_config.sh")
        subprocess.check_call(
            ['docker', 'save', metadata['docker_image_name']],
            stdout=open(metadata['genconf_tar'], 'w'))
        subprocess.check_call(['tar', 'cvf', '-', metadata['genconf_tar']], stdout=open('dcos_generate_config.sh', 'a'))
        subprocess.check_call(['chmod', '+x', 'dcos_generate_config.sh'])

    return metadata


def push_genconf_docker(metadata):
    channel_dest = "mesosphere/dcos-genconf:" + metadata['channel_name'].replace('/', '_')
    print("Pushing: {} and {}".format(metadata['docker_image_name'], channel_dest))
    subprocess.check_call(['docker', 'push', metadata['docker_image_name']])
    subprocess.check_call(['docker', 'tag', '-f', metadata['docker_image_name'], channel_dest])
    subprocess.check_call(['docker', 'push', channel_dest])


def make_abs(path):
    if path[0] == '/':
        return path
    return os.getcwd() + '/' + path


def do_create(options):
    channel_name = 'testing/' + options.destination_channel
    storage_providers = all_storage_providers(channel_name)
    channel = ChannelManager(storage_providers)
    commit = util.dcos_image_commit
    print("Creating release on channel:", channel_name)
    print("version tag:", options.tag)

    # TODO(cmaloney): Extract building genconf, checking these variables to a function.
    # Check needed configuration is set
    pkgpanda_src = make_abs(do_variable_set_or_exists('PKGPANDA_SRC', 'ext/pkgpanda'))
    dcos_image_src = make_abs(do_variable_set_or_exists('DCOS_IMAGE_SRC', os.getcwd()))

    # Build packages and generate bootstrap
    print("Building packages")
    # Build the standard docker build container, then build all the packages and bootstrap with it
    bootstrap_dict = do_build_packages(channel.repository_url, options.skip_build)

    default_bootstrap_id = bootstrap_dict[None]

    # Build all the per-provider templates
    # TODO(cmaloney): Allow making provider templates with non-default bootstrap
    # tarballs.
    print("Gathering per-provider additional files")
    provider_data, cleaned_provider_data = get_provider_data(
        channel.repository_url,
        default_bootstrap_id,
        options.tag,
        channel_name,
        commit)

    # TODO(cmaloney): Allow making a dcos-genconf docker which has a non-default
    # bootstrap tarball inside of it.
    print("Building dcos-genconf docker container")
    genconf_metadata = make_genconf_docker(pkgpanda_src, dcos_image_src, channel_name, default_bootstrap_id)

    # Calculate the active packages merged from all the bootstraps
    active_packages = set()
    for bootstrap_id in bootstrap_dict.values():
        active_packages |= get_bootstrap_packages(bootstrap_id)

    metadata_json = to_json(
        {
            'active_packages': list(active_packages),
            'bootstrap_dict': bootstrap_dict,
            'commit': commit,
            'date': util.template_generation_date,
            'provider_data': cleaned_provider_data,
            'tag': options.tag,
            'genconf_docker_tag': open('docker-tag').read()
        })

    # Upload packages, bootstrap.
    print("Uploading packages")
    if options.skip_upload:
        return

    channel.upload_packages(list(active_packages))
    channel.upload_bootstrap(bootstrap_dict)

    # TODO(cmaloney): Allow pushing multiple dcos-genconf docker, one for each bootstrap variant.
    # TODO(cmaloney): push the genconf docker into upload_providers_and_activate. Also copy the image
    # to have the channel name as a tag.
    print("Pushing dcos-genconf docker container")
    push_genconf_docker(genconf_metadata)

    # Upload provider artifacts, mark as active
    channel.upload_providers_and_activate(bootstrap_dict, commit, metadata_json, provider_data)
    print("New release created on channel", channel_name)


def validate_options(options):
    assert os.environ.get('AZURE_STORAGE_ACCOUNT'), 'Environment variable AZURE_STORAGE_ACCOUNT should be set'
    assert os.environ.get('AZURE_STORAGE_ACCESS_KEY'), 'Environment variable AZURE_STORAGE_ACCESS_KEY should be set'


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
        validate_options(options)
        options.func(options)
        sys.exit(0)
    else:
        parser.print_help()
        print("ERROR: Must use a subcommand")
        sys.exit(1)


if __name__ == '__main__':
    main()
