#!/usr/bin/env python3
"""DCOS release management

1. Build and upload a DCOS release to a release URL
2. Move a latest version of a release from one place to another

Co-ordinates across all providers.
"""

import abc
import argparse
import copy
import importlib
import json
import os.path
import subprocess
import sys
import tempfile

import azure.storage
import azure.storage.blob
import botocore.client
import pkgpanda
import pkgpanda.build
import pkgpanda.util

import providers.aws_config as aws_config
import providers.util as util

provider_names = ['aws', 'azure', 'vagrant']


def strip_locals(data):
    """Returns a dictionary with all keys that begin with local_ removed.

    If data is a dictionary, recurses through cleaning the keys of that as well.
    If data is a list, any dictionaries it contains are cleaned. Any lists it
    contains are recursively handled in the same way.

    """

    if isinstance(data, dict):
        data = copy.copy(data)
        for k in set(data.keys()):
            if isinstance(k, str) and k.startswith('local_'):
                del data[k]
            else:
                data[k] = strip_locals(data[k])
    elif isinstance(data, list):
        data = [strip_locals(item) for item in data]

    return data


def to_json(data):
    """Return a JSON string representation of data.

    If data is a dictionary, None is replaced with 'null' in its keys and,
    recursively, in the keys of any dictionary it contains. This is done to
    allow the dictionary to be sorted by key before being written to JSON.

    """
    def none_to_null(obj):
        try:
            items = obj.items()
        except AttributeError:
            return obj
        # Don't make any ambiguities by requiring null to not be a key.
        assert 'null' not in obj.keys()
        return {'null' if key is None else key: none_to_null(val) for key, val in items}

    return json.dumps(none_to_null(data), indent=2, sort_keys=True)


def from_json(json_str):
    """Reverses to_json"""

    def null_to_none(obj):
        try:
            items = obj.items()
        except AttributeError:
            return obj
        return {None if key == 'null' else key: null_to_none(val) for key, val in items}

    return null_to_none(json.loads(json_str))


def variant_str(variant):
    """Return a string representation of variant."""
    if variant is None:
        return ''
    return variant


def variant_name(variant):
    """Return a human-readable string representation of variant."""
    if variant is None:
        return '<default>'
    return variant


def variant_prefix(variant):
    """Return a filename prefix for variant."""
    if variant is None:
        return ''
    return variant + '.'


def get_bootstrap_packages(bootstrap_id):
    return set(pkgpanda.util.load_json('packages/{}.active.json'.format(bootstrap_id)))


def load_providers():
    modules = dict()
    for name in provider_names:
        modules[name] = importlib.import_module("providers." + name)
    return modules


class AbstractStorageProvider(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def copy(self,
             source_path,
             destination_path):
        """Copy the file and all metadata from destination_path to source_path."""
        pass

    @abc.abstractmethod
    def upload(self,
               destination_path,
               blob=None,
               local_path=None,
               no_cache=None,
               content_type=None):
        """Upload to destinoation_path the given blob or local_path, attaching metadata for additional properties."""
        pass

    @abc.abstractmethod
    def exists(self, path):
        """Return true iff the given file / path exists."""
        pass

    @abc.abstractmethod
    def fetch(self, path):
        """Download the given file and return bytes. Do not use on large files.

        Throw an exception if the path doesn't exist or is a folder."""
        pass

    @abc.abstractmethod
    def remove_recursive(self, path):
        """Recursively remove the given path. Should never error / always complete successfully.

        If the given path doesn't exist then just ignore and keep going.
        If the given path is a folder, delete all files and folders within it.
        If the given path is a file, delete the file and return."""
        pass

    @abc.abstractmethod
    def list_recursive(self, folder):
        """Return a set of the contents of the given folder and every subfolder with no metadata.

        Should return a set of filenames with the given folder prefix included.

        In a bucket containing blobs with the prefixes: bar, b/baz a/foo, a/folder/a, a/folder/b
        a call to list_recursive(a) would return: {"a/foo", "a/folder/a", "a/folder/b"}

        If given a file instead of a folder the behavior is unspecified."""
        pass

    @abc.abstractproperty
    def url(self):
        """The base url which should be used to fetch resources from this storage provider"""
        pass


class AzureStorageProvider(AbstractStorageProvider):
    name = 'azure'

    def __init__(self, account_name, account_key, container, dl_base_url):
        assert dl_base_url.endswith('/')
        self.container = container
        self.blob_service = azure.storage.blob.BlobService(account_name=account_name, account_key=account_key)
        self.__url = dl_base_url

    @property
    def url(self):
        return self.__url

    def copy(self, source_path, destination_path):
        assert destination_path[0] != '/'
        az_blob_url = self.blob_service.make_blob_url(self.container, source_path)

        # NOTE(cmaloney): The try / except on copy exception is ugly, but seems
        # to be necessary since sometimes we end up with hanging copy operations.
        resp = None
        try:
            resp = self.blob_service.copy_blob(self.container, destination_path, az_blob_url)
        except azure.common.AzureConflictHttpError:
            # Cancel the past copy, make a new copy
            properties = self.blob_service.get_blob_properties(self.container, destination_path)
            assert 'x-ms-copy-id' in properties
            self.blob_service.abort_copy_blob(self.container, destination_path, properties['x-ms-copy-id'])

            # Try the copy again
            resp = self.blob_service.copy_blob(self.container, destination_path, az_blob_url)

        # Since we're copying inside of one bucket the copy should always be
        # synchronous and successful.
        assert resp['x-ms-copy-status'] == 'success'

    def upload(self,
               destination_path,
               blob=None,
               local_path=None,
               no_cache=None,
               content_type=None):
        extra_args = {}

        if no_cache:
            extra_args['cache_control'] = None
        if content_type:
            extra_args['x_ms_blob_content_type'] = content_type

        # Must be a local_path or blob upload, not both
        assert local_path is None or blob is None
        if local_path:
            # Upload local_path
            self.blob_service.put_block_blob_from_path(
                self.container,
                destination_path,
                local_path,
                **extra_args)
        else:
            assert blob is not None
            assert isinstance(blob, bytes)
            self.blob_service.put_block_blob_from_text(
                self.container,
                destination_path,
                blob,
                **extra_args)

    def exists(self, path):
        try:
            self.blob_service.get_blob_properties(self.container, path)
            return True
        except azure.storage._common_error.AzureMissingResourceHttpError:
            return False

    def fetch(self, path):
        return self.blob_service.get_blob_to_bytes(self.container, path)

    def list_recursive(self, path):
        names = set()
        for blob in self.blob_service.list_blobs(self.container, path):
            names.add(blob.name)
        return names

    def remove_recursive(self, path):
        for blob_name in self.list_recursive(path):
            self.blob_service.delete_blob(self.container, blob_name)


class S3StorageProvider(AbstractStorageProvider):
    name = 'aws'

    def __init__(self, bucket, object_prefix, dl_base_url):
        assert not object_prefix.startswith('/')
        assert not object_prefix.endswith('/')
        self.__bucket = bucket
        self.__object_prefix = object_prefix
        self.__url = dl_base_url

    def _get_path(self, name):
        return self.__object_prefix + '/' + name

    def _get_objects_with_prefix(self, prefix):
        return self.__bucket.objects.filter(Prefix=self._get_path(prefix))

    def get_object(self, name):
        assert not name.startswith('/')
        return self.__bucket.Object(self._get_path(name))

    def fetch(self, path):
        body = self.get_object(path).get()['Body']
        data = bytes()
        for chunk in iter(lambda: body.read(4096), b''):
            data += chunk
        return data

    @property
    def url(self):
        return self.__url

    def copy(self, source_path, destination_path):
        src_object = self.get_object(source_path)
        new_object = self.get_object(destination_path)
        old_path = src_object.bucket_name + '/' + src_object.key

        new_object.copy_from(CopySource=old_path)

    def upload(self,
               destination_path,
               blob=None,
               local_path=None,
               no_cache=None,
               content_type=None):
        extra_args = {}
        if no_cache:
            extra_args['CacheControl'] = 'no-cache'
        if content_type:
            extra_args['ContentType'] = content_type

        s3_object = self.get_object(destination_path)

        assert local_path is None or blob is None
        if local_path:
            with open(local_path, 'rb') as data:
                s3_object.put(Body=data, **extra_args)
        else:
            assert isinstance(blob, bytes)
            s3_object.put(Body=blob, **extra_args)

    def exists(self, path):
        try:
            self.get_object(path).load()
            return True
        except botocore.client.ClientError:
            return False

    def list_recursive(self, path):
        prefix_len = len(self.__object_prefix + '/')
        names = set()
        for object_summary in self._get_objects_with_prefix(path):
            name = object_summary.key

            # Sanity check the prefix is there before removing.
            assert name.startswith(self.__object_prefix + '/')

            # Add the unprefixed name since the caller of this function doesn't
            # know we've added the prefix / only sees inside the prefix ever.
            names.add(name[prefix_len:])

        return names

    def remove_recursive(self, path):
        for obj in self._get_objects_with_prefix(path):
            obj.delete()


# Local storage provider useful for testing. Not used for the local artifacts
# since it would cause excess / needless copies, and doesn't work for "promote"
# since the artifacts won't be local (And downloading them all to be local
# would be a significant time sink).
class LocalStorageProvider(AbstractStorageProvider):
    name = 'local_storage_provider'

    def __init__(self, storage_path):
        assert isinstance(storage_path, str)
        assert not storage_path.endswith('/')
        self.__storage_path = storage_path

    def __full_path(self, path):
        return self.__storage_path + '/' + path

    def fetch(self, path):
        with open(self.__full_path(path), 'rb') as f:
            return f.read()

    # Copy between fully qualified paths
    def __copy(self, full_source_path, full_destination_path):
        subprocess.check_call(['mkdir', '-p', os.path.dirname(full_destination_path)])
        subprocess.check_call(['cp', full_source_path, full_destination_path])

    def copy(self, source_path, destination_path):
        self.__copy(self.__full_path(source_path), self.__full_path(destination_path))

    def upload(self, destination_path, blob=None, local_path=None, no_cache=None, content_type=None):
        # TODO(cmaloney): Don't discard the extra no_cache / content_type. We ideally want to be
        # able to test those are set.
        destination_full_path = self.__full_path(destination_path)
        subprocess.check_call(['mkdir', '-p', os.path.dirname(destination_full_path)])

        assert local_path is None or blob is None
        if local_path:
            self.__copy(local_path, destination_full_path)
        else:
            assert isinstance(blob, bytes)
            with open(destination_full_path, 'wb') as f:
                f.write(blob)

    def exists(self, path):
        assert path[0] != '/'
        return os.path.exists(self.__full_path(path))

    def remove_recursive(self, path):
        full_path = self.__full_path(path)

        # Make sure we're not going to delete something too horrible / in the
        # base system. Adjust as needed.
        assert len(path) > 5
        assert len(full_path) > 5
        subprocess.check_call(['rm', '-rf', full_path])

    def list_recursive(self, path):
        final_filenames = set()
        for dirpath, _, filenames in os.walk(self.__full_path(path)):
            assert dirpath.startswith(self.__storage_path)
            dirpath_no_prefix = dirpath[len(self.__storage_path)+1:]
            for filename in filenames:
                final_filenames.add(dirpath_no_prefix + '/' + filename)

        return final_filenames

    @property
    def url(self):
        return 'file://' + self.__storage_path + '/'


# Transforms artifact definitions from the Release Manager into sets of commands
# the storage providers understand, adding in the full path prefixes as needed
# so storage provides just have to know how to operate on paths rather than
# have all the logic about channels and repositories.
class Repository():

    def __init__(self, repository_path, channel_name, commit):
        if len(repository_path) == 0:
            raise ValueError("repository_path must be a non-empty string. channel_name may be None though.")

        assert not repository_path.endswith('/')
        if channel_name is not None:
            assert isinstance(channel_name, str)
            assert len(channel_name) > 0, "For an empty channel name pass None"
            assert not channel_name.startswith('/')
            assert not channel_name.endswith('/')
        assert '/' not in commit

        self.__repository_path = repository_path
        self.__channel_name = channel_name
        self.__commit = commit

    @property
    def channel_prefix(self):
        if self.__channel_name:
            return self.__channel_name + '/'
        else:
            return ''

    def channel_commit_path(self, artifact_path):
        assert artifact_path[0] != '/'
        return self.channel_path('commit/' + self.__commit + '/' + artifact_path)

    def channel_path(self, artifact_path):
        assert artifact_path[0] != '/'
        return self.repository_path(self.channel_prefix + artifact_path)

    def repository_path(self, artifact_path):
        assert artifact_path[0] != '/'

        return self.__repository_path + '/' + artifact_path

    # TODO(cmaloney): This function is too big. Break it into testable chunks.
    # TODO(cmaloney): Assert the same path/destination_path is never used twice.
    def make_commands(self, metadata, base_artifact_source):
        assert base_artifact_source['method'] in {'copy_from', 'upload'}

        stage1 = []
        stage2 = []
        local_cp = []

        def process_artifact(artifact, base_artifact):
            # First destination is upload
            # All other destinations are copies from first destination.
            upload_path = None

            def add_dest(destinoation_path, is_reproducible):
                nonlocal upload_path

                # First action -> upload
                # Future actions -> copy from upload / first action
                if upload_path is not None:
                    return {
                        'method': 'copy',
                        'if_not_exists': is_reproducible,
                        'args': {
                            'source_path': upload_path,
                            'destination_path': destinoation_path}}

                # Always set upload_path
                upload_path = destinoation_path

                # Copyfrom source method if a base artifact and we're supposed to get those by copying.
                if base_artifact and base_artifact_source['method'] == 'copy_from':
                    # Only reproducible artifacts / artifacts with a reproducible_path may be
                    # copied / moved from old repo.
                    assert is_reproducible
                    return {
                        'method': 'copy',
                        'if_not_exists': True,
                        'args': {
                            'source_path': base_artifact_source['repository'] + '/' + artifact['reproducible_path'],
                            'destination_path': destinoation_path}}
                else:
                    # Upload from local machine.
                    action = {
                        'method': 'upload',
                        'if_not_exists': is_reproducible,
                        'args': {
                            'destination_path': destinoation_path,
                            'no_cache': not is_reproducible}}
                    if 'local_path' in artifact:
                        # local_path and local_content are mutually exclusive / can only use one at a time.
                        assert 'local_content' not in artifact
                        action['args']['local_path'] = artifact['local_path']
                    elif 'local_content' in artifact:
                        action['args']['blob'] = artifact['local_content'].encode('utf-8')
                    else:
                        raise ValueError("local_path or local_content must be used as original source.")

                    if 'content_type' in artifact:
                        action['args']['content_type'] = artifact['content_type']
                    return action

            assert artifact.keys() <= {'reproducible_path', 'channel_path', 'content_type',
                                       'local_path', 'local_content'}

            action_count = 0
            if 'reproducible_path' in artifact:
                action_count += 1
                stage1.append(add_dest(self.repository_path(artifact['reproducible_path']), True))

            if 'channel_path' in artifact:
                channel_path = artifact['channel_path']
                action_count += 2
                stage1.append(add_dest(self.channel_commit_path(channel_path), False))
                stage2.append(add_dest(self.channel_path(channel_path), False))
                if 'local_path' in artifact:
                    local_cp.append({
                        'source_path': artifact['local_path'],
                        'destination_path': 'artifacts/' + channel_path})
                else:
                    assert 'local_content' in artifact
                    local_cp.append({
                        'source_content': artifact['local_content'],
                        'destination_path': 'artifacts/' + channel_path})

            # Must have done at least one thing with the artifact (reproducible_path or channel_path).
            assert action_count > 0

        for artifact in metadata['core_artifacts']:
            process_artifact(artifact, True)
        for artifact in metadata['channel_artifacts']:
            process_artifact(artifact, False)

        process_artifact({
            'channel_path': 'metadata.json',
            'content_type': 'application/json; charset=utf-8',
            'local_content': to_json(strip_locals(metadata))
            }, False)

        return {
            'stage1': stage1,
            'stage2': stage2,
            'local_cp': local_cp
        }


def get_package_artifact(package_id_str):
    package_id = pkgpanda.PackageId(package_id_str)
    package_filename = 'packages/{}/{}.tar.xz'.format(package_id.name, package_id_str)
    return {
        'reproducible_path': package_filename,
        'local_path': package_filename}


def make_stable_artifacts(cache_repository_url, skip_build):
    metadata = {
        "commit": util.dcos_image_commit,
        "core_artifacts": [],
        "packages": set()
    }

    # TODO(cmaloney): Rather than guessing / reverse-engineering all these paths
    # have do_build_packages get them directly from pkgpanda
    bootstrap_dict = do_build_packages(cache_repository_url, skip_build)
    metadata["bootstrap_dict"] = bootstrap_dict

    def add_file(info):
        metadata["core_artifacts"].append(info)

    def add_package(package_id):
        if package_id in metadata['packages']:
            return
        metadata['packages'].add(package_id)
        add_file(get_package_artifact(package_id))

    # Add the bootstrap, active.json, packages as reproducible_path artifacts
    # Add the <variant>.bootstrap.latest as a channel_path
    for name, bootstrap_id in bootstrap_dict.items():
        bootstrap_filename = "{}.bootstrap.tar.xz".format(bootstrap_id)
        add_file({
            'reproducible_path': 'bootstrap/' + bootstrap_filename,
            'local_path': 'packages/' + bootstrap_filename
            })
        active_filename = "{}.active.json".format(bootstrap_id)
        add_file({
            'reproducible_path': 'bootstrap/' + active_filename,
            'local_path': 'packages/' + active_filename
            })
        latest_filename = "{}bootstrap.latest".format(variant_prefix(name))
        add_file({
            'channel_path': latest_filename,
            'local_path': 'packages/' + latest_filename
            })

        # Add all the packages which haven't been added yet
        for package_id in sorted(get_bootstrap_packages(bootstrap_id)):
            add_package(package_id)

    # Sets aren't json serializable, so transform to a list for future use.
    metadata['packages'] = list(sorted(metadata['packages']))

    return metadata


# Generate provider templates against the bootstrap id, capturing the
# needed packages.
# {
#   <provider_name>: {
#     'extra_packages': [],
#     'files': [{
#        # NOTE: May specify a list of known_names
#       'known_path': 'cloudformation/single-master.cloudformation.json',
#       'stable_path': 'cloudformation/{}.cloudformation.json',
#        # NOTE: Only one of content or content_file is allowed
#       'content': '',
#       'content_file': '',
#       }]}}
def make_channel_artifacts(metadata):
    artifacts = []

    installers = build_installers(metadata['bootstrap_dict'])

    artifacts.append({'channel_path': 'docker-tag', 'local_content': installers[None][0]})
    artifacts.append({'channel_path': 'docker-tag.txt', 'local_content': installers[None][0]})

    # Add installer scripts for all bootstraps.
    for variant, (installer_version, installer_filename) in installers.items():
        artifacts.append({
            'channel_path': 'dcos_generate_config.{}sh'.format(variant_prefix(variant)),
            'local_path': installer_filename
            })

    provider_data = {}
    providers = load_providers()
    for name, module in sorted(providers.items()):
        bootstrap_url = metadata['repository_url']

        # If the particular provider has its own storage by the same name then
        # Use the storage provider rather
        if name in metadata['storage_urls']:
            bootstrap_url = metadata['storage_urls'][name] + metadata['repository_path']

        # Add templates for the default variant.
        # Use keyword args to make not matching ordering a loud error around changes.
        provider_data = module.do_create(
            tag=metadata['tag'],
            repo_channel_path=metadata['repo_channel_path'],
            channel_commit_path=metadata['channel_commit_path'],
            commit=metadata['commit'],
            gen_arguments=copy.deepcopy({
                'bootstrap_id': metadata['bootstrap_dict'][None],
                'bootstrap_url': bootstrap_url,
                'provider': name
            }))

        # Translate provider data to artifacts
        assert provider_data.keys() <= {'packages', 'artifacts'}

        for package in provider_data.get('packages', set()):
            artifacts.append(get_package_artifact(package))

        # TODO(cmaloney): Check the provider artifacts adhere to the artifact template.
        artifacts += provider_data.get('artifacts', list())

    return artifacts


def make_abs(path):
    if path[0] == '/':
        return path
    return os.getcwd() + '/' + path


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


def get_src_dirs():
    pkgpanda_src = make_abs(do_variable_set_or_exists('PKGPANDA_SRC', 'ext/pkgpanda'))
    dcos_image_src = make_abs(do_variable_set_or_exists('DCOS_IMAGE_SRC', os.getcwd()))
    dcos_installer_src = make_abs(do_variable_set_or_exists('DCOS_INSTALLER_SRC', 'ext/dcos-installer'))

    return pkgpanda_src, dcos_image_src, dcos_installer_src


def do_build_packages(cache_repository_url, skip_build):
    dockerfile = 'docker/builder/Dockerfile'
    container_name = 'mesosphere/dcos-builder:dockerfile-' + pkgpanda.build.sha1(dockerfile)
    print("Attempting to pull dcos-builder docker:", container_name)
    pulled = False
    try:
        # TODO(cmaloney): Rather than pushing / pulling from Docker Hub upload as a build artifact.
        # the exported tarball.
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

    def get_build():
        # TODO(cmaloney): Stop shelling out
        if not skip_build:
            subprocess.check_call(
                ['mkpanda', 'tree', '--mkbootstrap', '--repository-url=' + cache_repository_url],
                cwd='packages',
                env=os.environ)

        return pkgpanda.build.get_last_bootstrap_set('packages')

    return get_build()


def make_installer_docker(variant, bootstrap_id):
    assert len(bootstrap_id) > 0

    # TODO(cmaloney): If a pre-existing wheelhouse exists assert that the wheels
    # inside of it match the current versions / working commits of pkganda, dcos-image.
    pkgpanda_src, dcos_image_src, dcos_installer_src = get_src_dirs()
    wheel_dir = os.getcwd() + '/wheelhouse'
    if not os.path.exists(wheel_dir):
        print("Building wheels for dcos-image, pkgpanda, and all dependencies")

        # Make the wheels
        subprocess.check_call(['pip', 'wheel', pkgpanda_src])
        subprocess.check_call(['pip', 'wheel', dcos_image_src])
        subprocess.check_call(['pip', 'wheel', dcos_installer_src])

    image_version = util.dcos_image_commit[:18] + '-' + bootstrap_id[:18]
    genconf_tar = "dcos-genconf." + image_version + ".tar"
    installer_filename = "dcos_generate_config." + variant_prefix(variant) + "sh"
    bootstrap_filename = bootstrap_id + ".bootstrap.tar.xz"
    bootstrap_path = os.getcwd() + "/packages/" + bootstrap_filename

    metadata = {
        'variant': variant_name(variant),
        'bootstrap_id': bootstrap_id,
        'docker_tag': image_version,
        'genconf_tar': genconf_tar,
        'bootstrap_filename': bootstrap_filename,
        'bootstrap_path': bootstrap_path,
        'docker_image_name': 'mesosphere/dcos-genconf:' + image_version,
        'dcos_image_commit': util.dcos_image_commit,
        'variant': variant
    }

    with tempfile.TemporaryDirectory() as build_dir:
        assert build_dir[-1] != '/'

        pkgpanda.util.write_string(
            build_dir + '/Dockerfile',
            pkgpanda.util.load_string('docker/installer/Dockerfile.template').format(**metadata))

        pkgpanda.util.write_string(
            installer_filename,
            pkgpanda.util.load_string('docker/installer/dcos_generate_config.sh.in').format(**metadata) + '\n#EOF#\n')

        # Copy across the wheelhouse
        subprocess.check_call(['cp', '-r', wheel_dir, build_dir + '/wheelhouse'])

        print("Pulling base docker")
        subprocess.check_call(['docker', 'pull', 'python:3.4.3-slim'])

        print("Building docker container in " + build_dir)
        subprocess.check_call(['cp', metadata['bootstrap_path'], build_dir + '/' + metadata['bootstrap_filename']])
        subprocess.check_call(['docker', 'build', '-t', metadata['docker_image_name'], build_dir])

        print("Building", installer_filename)
        subprocess.check_call(
            ['docker', 'save', metadata['docker_image_name']],
            stdout=open(metadata['genconf_tar'], 'w'))
        subprocess.check_call(['tar', 'cvf', '-', metadata['genconf_tar']], stdout=open(installer_filename, 'a'))
        subprocess.check_call(['chmod', '+x', installer_filename])

    return image_version, installer_filename


def build_installers(bootstrap_dict):
    """Create a installer script for each variant in bootstrap_dict.

    Writes a dcos_generate_config.<variant>.sh for each variant in
    bootstrap_dict to the working directory, except for the default variant's
    script, which is written to dcos_generate_config.sh. Returns a dict mapping
    variants to (genconf_version, genconf_filename) tuples.

    """
    installers = {}

    # TODO(cmaloney): Build installers in parallel.
    # Variants are sorted for stable ordering.
    for variant, bootstrap_id in sorted(bootstrap_dict.items(), key=lambda kv: variant_str(kv[0])):
        print("Building installer for variant:", variant_name(variant))
        installers[variant] = make_installer_docker(variant, bootstrap_id)
    return installers


def validate_options(options):
    assert os.environ.get('AZURE_STORAGE_ACCOUNT'), 'Environment variable AZURE_STORAGE_ACCOUNT should be set'
    assert os.environ.get('AZURE_STORAGE_ACCESS_KEY'), 'Environment variable AZURE_STORAGE_ACCESS_KEY should be set'

    # Validate src_dirs are set properly up front. Building per channel
    # artifacts will fail without it.
    get_src_dirs()


# Two stages of uploading artifacts. First puts all the artifacts into their places / uploads
# all the artifacts to all providers. The second makes the end user known / used urls have the
# correct artifacts.
# The split is because in order to use some artifacts (Such as the cloudformation template) other
# artifacts must already be in place. All those artifacts which must be in place get uploaded in
# upload artifacts. By having the two steps we guarantee that a user is never able to download
# something such as a cloudformation template which won't work.
class ReleaseManager():
    def __init__(self, storage_providers, preferred_provider, noop):
        self.__storage_providers = storage_providers
        self.__noop = noop
        self.__preferred_provider = storage_providers[preferred_provider]

    def get_metadata(src_channel):
        return from_json(self.__preferred_provider.fetch(src_channel + '/metadata.json'))

    def promote(self, src_channel, destination_channel):
        metadata = self.get_metadata(src_channel)
        src_repository_path = metadata['repository']

        # Can't run a release promotion with a different version of the scripts than the one that
        # created the release.
        assert metadata['commit'] == util.dcos_image_commit

        # TODO(cmaloney): Make key stable artifacts local (bootstrap) so they
        # can be used / referenced inside the per-channel artifacts.
        self.fetch_key_artifacts(metadata)

        repository = Repository(destination_channel, None, metadata['commit'])

        metadata['repository_path'] = destination_channel
        metadata['repository_url'] = self.__preferred_provider.url + destination_channel
        metadata['repo_channel_path'] = destination_channel
        # Check that the channel_commit_path ends in a '/'. We want the metadata we add to not end
        # in a slash, so we remove that. We aren't allowed to call the channel_commit_path with a
        # non-empty artifact path, so use 'a' as a placeholder.
        assert repository.channel_commit_path('a')[-2:] == '/a'
        metadata['channel_commit_path'] = repository.channel_commit_path('a')[:-2]
        metadata['storage_urls'] = {}
        for name, store in self.__storage_providers.items():
            metadata['storage_urls'][name] = store.url
        del metadata['channel_artifacts']

        metadata['channel_artifacts'] = make_channel_artifacts(metadata)

        storage_commands = repository.make_commands(
            metadata,
            base_artifacts={'method': 'copy_from', 'repository': src_repository_path})
        self.apply_storage_commands(storage_commands)

        return metadata

    def create(self, repository_path, channel, tag, skip_build):
        assert len(channel) > 0  # channel must be a non-empty string.

        # TOOD(cmaloney): Figure out why the cached version hasn't been working right
        # here from the TeamCity agents. For now hardcoding the non-cached s3 download locatoin.
        repository_url = self.__preferred_provider.url + repository_path
        metadata = make_stable_artifacts(
            'https://s3.amazonaws.com/downloads.mesosphere.io/dcos/' + repository_path, skip_build)

        # Metadata should already have things like bootstrap_id in it.
        assert 'bootstrap_dict' in metadata
        assert 'commit' in metadata

        repository = Repository(repository_path, channel, metadata['commit'])
        metadata['repo_channel_path'] = repository_path + '/' + channel
        # Check that the channel_commit_path ends in a '/'. We want the metadata we add to not end
        # in a slash, so we remove that. We aren't allowed to call the channel_commit_path with a
        # non-empty artifact path, so use 'a' as a placeholder.
        assert repository.channel_commit_path('a')[-2:] == '/a'
        metadata['channel_commit_path'] = repository.channel_commit_path('a')[:-2]
        metadata['storage_urls'] = {}
        for name, store in self.__storage_providers.items():
            metadata['storage_urls'][name] = store.url

        metadata['repository_path'] = repository_path
        metadata['repository_url'] = repository_url
        metadata['tag'] = tag
        assert 'channel_artifacts' not in metadata

        metadata['channel_artifacts'] = make_channel_artifacts(metadata)

        storage_commands = repository.make_commands(metadata, {'method': 'upload'})
        self.apply_storage_commands(storage_commands)

        return metadata

    def apply_storage_commands(self, storage_commands):
        assert storage_commands.keys() == {'stage1', 'stage2', 'local_cp'}

        if self.__noop:
            return

        # TODO(cmaloney): Use a multiprocessing map to do all storage providers in parallel.
        for stage in ['stage1', 'stage2']:
            commands = storage_commands[stage]
            for provider_name, provider in self.__storage_providers.items():
                for artifact in commands:
                    path = artifact['args']['destination_path']
                    # If it is only supposed to be if the artifact does not exist, check for existence
                    # and skip if it exists.
                    if artifact['if_not_exists'] and provider.exists(path):
                        print("Store to", provider_name, "artifact", path, "skipped because it already exists")
                        continue
                    print("Store to", provider_name, "artifact", path, "by method", artifact['method'])
                    getattr(provider, artifact['method'])(**artifact['args'])

        for artifact in storage_commands['local_cp']:
            destination_path = artifact['destination_path']
            print("Saving to local artifact path", destination_path)
            subprocess.check_call(['mkdir', '-p', os.path.dirname(destination_path)])
            if 'source_path' in artifact:
                subprocess.check_call(['cp', artifact['source_path'], destination_path])
            else:
                assert 'source_content' in artifact
                pkgpanda.util.write_string(destination_path, artifact['source_content'])


def get_prod_storage_providers():
    azure_account_name = os.environ['AZURE_STORAGE_ACCOUNT']
    azure_account_key = os.environ['AZURE_STORAGE_ACCESS_KEY']

    s3_bucket = aws_config.session_prod.resource('s3').Bucket('downloads.mesosphere.io')

    storage_providers = {
        'azure': AzureStorageProvider(azure_account_name, azure_account_key, 'dcos',
                                      'http://az837203.vo.msecnd.net/dcos/'),
        'aws': S3StorageProvider(s3_bucket, 'dcos', 'https://downloads.mesosphere.com/dcos/')
    }

    for name, provider in storage_providers.items():
        assert provider.name == name

    return storage_providers


def main():
    parser = argparse.ArgumentParser(description='DCOS Release Management Tool.')
    subparsers = parser.add_subparsers(title='commands')

    parser.add_argument(
        '--noop',
        action='store_true',
        help="Do not take any actions on the storage providers, just run the "
             "whole build, produce the list of actions than no-op.")

    # Moves the latest of a given release name to the given release name.
    promote = subparsers.add_parser('promote')
    promote.set_defaults(action='promote')
    promote.add_argument('source_channel')
    promote.add_argument('destination_repoistory')
    promote.add_argument('destination_channel')

    # Creates, uploads, and marks as latest.
    # The marking as latest is ideally atomic (At least all artifacts when they
    # are uploaded should never result in a state where things don't work).
    create = subparsers.add_parser('create')
    create.set_defaults(action='create')
    create.add_argument('channel')
    create.add_argument('tag')
    create.add_argument('--skip-build', action='store_true')

    # Parse the arguments and dispatch.
    options = parser.parse_args()
    if not hasattr(options, 'action'):
        parser.print_help()
        print("ERROR: Must use a subcommand")
        sys.exit(1)

    validate_options(options)
    release_manager = ReleaseManager(get_prod_storage_providers(), 'aws', options.noop)
    if options.action == 'promote':
        release_manager.promote(options.source_channel, options.destination_channel)
    elif options.action == 'create':
        release_manager.create('testing', options.channel, options.tag, options.skip_build)
    else:
        raise ValueError("Unexpection options.action {}".format(options.action))


if __name__ == '__main__':
    main()
