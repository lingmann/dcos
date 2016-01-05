import copy
import os
import subprocess
import uuid

import pytest
from pkgpanda.util import write_json, write_string

import providers.aws_config
import providers.release as release


def roundtrip_to_json(data, mid_state, new_end_state=None):
    assert release.to_json(data) == mid_state

    if new_end_state is not None:
        assert release.from_json(mid_state) == new_end_state
    else:
        assert release.from_json(mid_state) == data


def test_to_json():
    roundtrip_to_json('foo', '"foo"')
    roundtrip_to_json(['foo', 'bar'], '[\n  "foo",\n  "bar"\n]')
    roundtrip_to_json(('foo', 'bar'), '[\n  "foo",\n  "bar"\n]', ['foo', 'bar'])
    roundtrip_to_json({'foo': 'bar', 'baz': 'qux'}, '{\n  "baz": "qux",\n  "foo": "bar"\n}')

    # Sets aren't JSON serializable.
    with pytest.raises(TypeError):
        release.to_json({'foo', 'bar'})


def test_dict_to_json():
    # None in keys is converted to "null".
    roundtrip_to_json({None: 'foo'}, '{\n  "null": "foo"\n}')

    # Keys in resulting objects are sorted.
    roundtrip_to_json({None: 'baz', 'foo': 'bar'}, '{\n  "foo": "bar",\n  "null": "baz"\n}')

    # Nested dicts are processed too.
    roundtrip_to_json(
        {'foo': {'bar': 'baz', None: 'qux'}, None: 'quux'},
        '{\n  "foo": {\n    "bar": "baz",\n    "null": "qux"\n  },\n  "null": "quux"\n}')

    # Input isn't mutated.
    actual = {'foo': 'bar', None: {'baz': 'qux', None: 'quux'}}
    expected = copy.deepcopy(actual)
    release.to_json(actual)
    assert actual == expected


def test_strip_locals():
    # Raw pass through non-dictionary-like things
    assert release.strip_locals('foo') == 'foo'
    assert release.strip_locals(['a', 'b']) == ['a', 'b']

    # Dictionaries get all local_ keys removed
    assert release.strip_locals({'a': 'b', 'foo_local': 'foo'}) == {'a': 'b', 'foo_local': 'foo'}
    assert release.strip_locals({'local_a': 'foo'}) == {}
    assert release.strip_locals({'local_a': 'foo', None: 'foo'}) == {None: 'foo'}
    assert release.strip_locals({'a': 1, 'local_a': 3.4}) == {'a': 1}
    assert release.strip_locals({'local_a': 'foo', 'local_path': '/test', 'foobar': 'baz'}) == {'foobar': 'baz'}
    assert release.strip_locals({'local_a': 'foo', 'local_path': '/test'}) == {}

    # Test the recursive case, as well as that the source dictionary isn't modified.
    src_dict = {'a': {'local_a': 'foo'}, 'local_b': '/test', 'c': {'d': 'e', 'f': 'g'}}
    assert release.strip_locals(src_dict) == {'a': {}, 'c': {'d': 'e', 'f': 'g'}}
    assert src_dict == {'a': {'local_a': 'foo'}, 'local_b': '/test', 'c': {'d': 'e', 'f': 'g'}}


def test_variant_variations():
    assert release.variant_str(None) == ''
    assert release.variant_str('test') == 'test'

    assert release.variant_name(None) == '<default>'
    assert release.variant_name('test') == 'test'

    assert release.variant_prefix(None) == ''
    assert release.variant_prefix('test') == 'test.'


def exercise_storage_provider(tmpdir, storage_provider):
    # Alias to reduce typing
    store = storage_provider

    # Make a uniquely named test storage location, and try to upload / copy files
    # inside that location.
    test_id = uuid.uuid4().hex
    test_base_path = 'dcos-image-test-tmp/{}'.format(test_id)

    # We want to always disable caching and set content-type so that things work
    # right when debugging the tests.
    upload_extra_args = {
        'no_cache': True,
        'content_type': 'text/plain; charset=utf-8'
    }

    # Test we're starting with an empty test_base_path
    assert store.list_recursive(test_base_path) == set()

    # TODO(cmaloney): Add a test that uses different caching, content-type,
    # and checks that the caching of the url download location works properly
    # as well as the properties get carried through copies.

    assert store.url.endswith('/')

    def curl_fetch(path):
        return subprocess.check_output([
            'curl',
            '--fail',
            '--location',
            '--silent',
            '--show-error',
            '--verbose',
            store.url + path])

    def get_path(path):
        assert not path.startswith('/')
        return test_base_path + '/' + path

    def check_file(path, contents):
        # The store should be internally consistent / API return it exists now.
        assert store.exists(path)

        # We should be able to use the native fetching method.
        assert store.fetch(path) == contents

        # Other programs should be able to fetch with curl.
        assert curl_fetch(path) == contents

    def make_content(name):
        return (name + " " + uuid.uuid4().hex).encode()

    try:
        # Test uploading bytes.
        upload_bytes = make_content("upload_bytes")
        upload_bytes_path = get_path('upload_bytes.txt')
        store.upload(
            upload_bytes_path,
            blob=upload_bytes,
            **upload_extra_args)
        check_file(upload_bytes_path, upload_bytes)

        # Test uploading the same bytes to a non-existent subdirectory of a subdirectory
        upload_bytes_dir_path = get_path("dir1/bar/upload_bytes2.txt")
        store.upload(
            upload_bytes_dir_path,
            blob=upload_bytes,
            **upload_extra_args)

        # Test uploading a local file.
        upload_file = make_content("upload_file")
        upload_file_path = get_path('upload_file.txt')
        upload_file_local = tmpdir.join('upload_file.txt')
        upload_file_local.write(upload_file)
        store.upload(
            upload_file_path,
            local_path=str(upload_file_local),
            **upload_extra_args)
        check_file(upload_file_path, upload_file)

        # Test copying uploaded bytes.
        copy_dest_path = get_path('copy_file.txt')
        store.copy(upload_bytes_path, copy_dest_path)
        check_file(copy_dest_path, upload_bytes)

        # Test copying an uploaded file to a subdirectory.
        copy_dest_path = get_path('new_dir/copy_path.txt')
        store.copy(upload_file_path, copy_dest_path)
        check_file(copy_dest_path, upload_file)

        # Check that listing all the files in the storage provider gives the list of
        # files we've uploaded / checked and only that list of files.
        assert store.list_recursive(test_base_path) == {
            get_path('upload_file.txt'),
            get_path('upload_bytes.txt'),
            get_path('dir1/bar/upload_bytes2.txt'),
            get_path('new_dir/copy_path.txt'),
            get_path('copy_file.txt')
        }

        # Check that cleanup removes everything
        store.remove_recursive(test_base_path)
        assert store.list_recursive(test_base_path) == set()
    finally:
        # Cleanup temp directory in storage provider as best as possible.
        storage_provider.remove_recursive(test_base_path)


# TODO(cmaloney): Add skipping when not run under CI with the environment variables
# So devs without the variables don't see expected failures https://pytest.org/latest/skipping.html
def test_storage_provider_azure(tmpdir):
    azure_account_name = os.environ['AZURE_DEV_STORAGE_ACCOUNT']
    azure_account_key = os.environ['AZURE_DEV_STORAGE_ACCESS_KEY']
    exercise_storage_provider(
        tmpdir,
        release.AzureStorageProvider(
            azure_account_name,
            azure_account_key,
            'dcos-image-test',
            'https://mesospheredev.blob.core.windows.net/dcos-image-test/'))

s3_test_bucket_all_read_policy = """{
    "Version": "2008-10-17",
    "Statement": [
        {
            "Sid": "AddPerm",
            "Effect": "Allow",
            "Principal": {
                "AWS": "*"
            },
            "Action": "s3:GetObject",
            "Resource": "arn:aws:s3:::dcos-image-unit-tests/*"
        }
    ]
}"""


# TODO(cmaloney): Add skipping when not run under CI with the environment variables
# So devs without the variables don't see expected failures https://pytest.org/latest/skipping.html
def test_storage_provider_aws(tmpdir):
    s3_bucket = providers.aws_config.session_dev.resource('s3').Bucket('dcos-image-unit-tests')

    # Make the bucket if it doesn't exist / was cleaned up. S3 doesn't error on repeated creation.
    s3_bucket.create()
    s3_bucket.Policy().put(Policy=s3_test_bucket_all_read_policy)

    # Work inside the bucket.
    exercise_storage_provider(
        tmpdir,
        release.S3StorageProvider(
            s3_bucket,
            'test_storage_provider',
            'https://s3.amazonaws.com/dcos-image-unit-tests/test_storage_provider/'))


def test_storage_provider_local(tmpdir):
    work_dir = tmpdir.mkdir("work")
    repo_dir = tmpdir.mkdir("repository")
    exercise_storage_provider(work_dir, release.LocalStorageProvider(str(repo_dir)))


copy_make_commands_result = {'stage1': [
    {
        'if_not_exists': True,
        'args': {
            'source_path': '/test_source_repo/1.html',
            'destination_path': 'stable/1.html'},
        'method': 'copy'},
    {
        'if_not_exists': True,
        'args': {
            'source_path': '/test_source_repo/3.html',
            'destination_path': 'stable/3.html'},
        'method': 'copy'},
    {
        'if_not_exists': False,
        'args': {
            'source_path': 'stable/3.html',
            'destination_path': 'stable/commit/testing_commit_2/3.html'},
        'method': 'copy'},
    {
        'if_not_exists': True,
        'args': {
            'source_path': '/test_source_repo/3.json',
            'destination_path': 'stable/3.json'},
        'method': 'copy'},
    {
        'if_not_exists': False,
        'args': {
            'source_path': 'stable/3.json',
            'destination_path': 'stable/commit/testing_commit_2/3.json'},
        'method': 'copy'},
    {
        'if_not_exists': False,
        'args': {
            'no_cache': True,
            'destination_path': 'stable/commit/testing_commit_2/2.html',
            'blob': b'2'},
        'method': 'upload'},
    {
        'if_not_exists': False,
        'args': {
            'no_cache': True,
            'destination_path': 'stable/commit/testing_commit_2/cf.json',
            'blob': b'{"a": "b"}',
            'content_type': 'application/json'},
        'method': 'upload'},
    {
        'if_not_exists': True,
        'args': {
            'no_cache': False,
            'destination_path': 'stable/some_big_hash.txt',
            'blob': b'hashy'},
        'method': 'upload'},
    {
        'if_not_exists': False,
        'args': {
            'no_cache': True,
            'destination_path': 'stable/commit/testing_commit_2/metadata.json',
            'blob': b'{\n  "channel_artifacts": [\n    {\n      "channel_path": "2.html",\n      "local_content": "2"\n    },\n    {\n      "channel_path": "cf.json",\n      "content_type": "application/json",\n      "local_content": "{\\"a\\": \\"b\\"}"\n    },\n    {\n      "local_content": "hashy",\n      "reproducible_path": "some_big_hash.txt"\n    }\n  ],\n  "core_artifacts": [\n    {\n      "local_content": "1",\n      "reproducible_path": "1.html"\n    },\n    {\n      "channel_path": "3.html",\n      "content_type": "text/html",\n      "local_content": "3",\n      "reproducible_path": "3.html"\n    },\n    {\n      "channel_path": "3.json",\n      "content_type": "application/json",\n      "local_path": "/test/foo.json",\n      "reproducible_path": "3.json"\n    }\n  ],\n  "foo": "bar"\n}',  # noqa
            'content_type': 'application/json; charset=utf-8'},
        'method': 'upload'}
    ],
    'stage2': [{
        'if_not_exists': False,
        'args': {
            'source_path': 'stable/3.html',
            'destination_path': 'stable/3.html'},
        'method': 'copy'},
    {
        'if_not_exists': False,
        'args': {
            'source_path': 'stable/3.json',
            'destination_path': 'stable/3.json'},
        'method': 'copy'},
    {
        'if_not_exists': False,
        'args': {
            'source_path': 'stable/commit/testing_commit_2/2.html',
            'destination_path': 'stable/2.html'},
        'method': 'copy'},
    {
        'if_not_exists': False,
        'args': {
            'source_path': 'stable/commit/testing_commit_2/cf.json',
            'destination_path': 'stable/cf.json'},
        'method': 'copy'},
    {
        'if_not_exists': False,
        'args': {
            'source_path': 'stable/commit/testing_commit_2/metadata.json',
            'destination_path': 'stable/metadata.json'},
        'method': 'copy'}
    ],
    'local_cp': [{
        'destination_path': 'artifacts/3.html',
        'source_content': '3'},
    {
        'source_path': '/test/foo.json',
        'destination_path': 'artifacts/3.json'},
    {
        'destination_path': 'artifacts/2.html',
        'source_content': '2'},
    {
        'destination_path': 'artifacts/cf.json',
        'source_content': '{"a": "b"}'},
    {
        'destination_path': 'artifacts/metadata.json',
        'source_content': '{\n  "channel_artifacts": [\n    {\n      "channel_path": "2.html",\n      "local_content": "2"\n    },\n    {\n      "channel_path": "cf.json",\n      "content_type": "application/json",\n      "local_content": "{\\"a\\": \\"b\\"}"\n    },\n    {\n      "local_content": "hashy",\n      "reproducible_path": "some_big_hash.txt"\n    }\n  ],\n  "core_artifacts": [\n    {\n      "local_content": "1",\n      "reproducible_path": "1.html"\n    },\n    {\n      "channel_path": "3.html",\n      "content_type": "text/html",\n      "local_content": "3",\n      "reproducible_path": "3.html"\n    },\n    {\n      "channel_path": "3.json",\n      "content_type": "application/json",\n      "local_path": "/test/foo.json",\n      "reproducible_path": "3.json"\n    }\n  ],\n  "foo": "bar"\n}'  # noqa
    }
]}

upload_make_command_results = {
    'local_cp': [{
        'destination_path':
        'artifacts/metadata.json',
        'source_content': '{\n  "channel_artifacts": [],\n  "core_artifacts": [\n    {\n      "local_content": "foo",\n      "reproducible_path": "foo"\n    }\n  ]\n}'}],  # noqa
    'stage2': [{
        'args': {
            'source_path': 'stable/commit/testing_commit_2/metadata.json',
            'destination_path': 'stable/metadata.json'},
            'method': 'copy',
            'if_not_exists': False}],
    'stage1': [{
        'args': {
            'no_cache': False,
            'destination_path':
            'stable/foo',
            'blob': b'foo'},
        'method': 'upload',
        'if_not_exists': True},
    {
        'args': {
            'no_cache': True,
            'destination_path': 'stable/commit/testing_commit_2/metadata.json',
            'blob': b'{\n  "channel_artifacts": [],\n  "core_artifacts": [\n    {\n      "local_content": "foo",\n      "reproducible_path": "foo"\n    }\n  ]\n}', 'content_type': 'application/json; charset=utf-8'},  # noqa
        'method': 'upload',
        'if_not_exists': False}
    ]}


def exercise_make_commands(repository):
    # Run make_commands on multiple different artifact
    # lists, make sure the output artifact list are what is expected given the
    # channel_prefix, channel_commit_path, channel_path, and repository_path
    # members.
    copy_source = {'method': 'copy_from', 'repository': '/test_source_repo'}
    upload_source = {'method': 'upload'}

    # TODO(cmaloney): Rather than one big make_commands test each different
    # artifact separately to make test failures more understandable, extending
    # as changes happen easier.
    # A list of artifacts that includes every attribute an artifact can have
    reproducible_artifacts = [
        {
            'reproducible_path': '1.html',
            'local_content': '1'
        },
        {
            'reproducible_path': '3.html',
            'channel_path': '3.html',
            'local_content': '3',
            'content_type': 'text/html'
        },
        {
            'reproducible_path': '3.json',
            'channel_path': '3.json',
            'local_path': '/test/foo.json',
            'content_type': 'application/json'
        },
    ]

    channel_artifacts = [
        {
            'channel_path': '2.html',
            'local_content': '2'
        },
        {
            'channel_path': 'cf.json',
            'local_content': '{"a": "b"}',
            'content_type': 'application/json'
        },
        {
            'reproducible_path': 'some_big_hash.txt',
            'local_content': 'hashy',
        }
    ]

    metadata = {
        'foo': 'bar',
        'core_artifacts': reproducible_artifacts,
        'channel_artifacts': channel_artifacts
    }

    assert repository.make_commands(metadata, copy_source) == copy_make_commands_result

    upload_could_copy_artifacts = [{
        'reproducible_path': 'foo',
        'local_content': 'foo'}]

    # Test a single simple artifact which should hit the upload logic rather than copy
    simple_artifacts = {'core_artifacts': upload_could_copy_artifacts, 'channel_artifacts': []}
    assert repository.make_commands(simple_artifacts, upload_source) == upload_make_command_results


def test_repository():
    # Must specify a repository path
    with pytest.raises(ValueError):
        release.Repository("", None, "testing_commit")

    # For an empty channel name, use None
    with pytest.raises(AssertionError):
        release.Repository("foo", "", "testing_commit")

    # Repository path with no channel (Like we'd do for a stable or EA release).
    no_channel = release.Repository("stable", None, "testing_commit_2")
    assert no_channel.channel_prefix == ''
    assert no_channel.channel_commit_path("foo") == 'stable/commit/testing_commit_2/foo'
    assert no_channel.channel_path("bar") == 'stable/bar'
    assert no_channel.repository_path("a/baz--foo.tar.xz") == 'stable/a/baz--foo.tar.xz'
    exercise_make_commands(no_channel)

    # Repository path with a channel (Like we do for PRs)
    with_channel = release.Repository("testing", "pull/283", "testing_commit_3")
    assert with_channel.channel_prefix == 'pull/283/'
    assert with_channel.channel_commit_path("foo") == 'testing/pull/283/commit/testing_commit_3/foo'
    assert with_channel.channel_path("bar") == 'testing/pull/283/bar'
    assert with_channel.repository_path("a/baz--foo.tar.xz") == 'testing/a/baz--foo.tar.xz'
    # TODO(cmaloney): Exercise make_commands with a channel.


def test_get_package_artifact(tmpdir):
    assert release.get_package_artifact('foo--test') == {
        'reproducible_path': 'packages/foo/foo--test.tar.xz',
        'local_path': 'packages/foo/foo--test.tar.xz'
    }


def mock_do_build_packages(cache_repository_url, skip_build):
    subprocess.check_call(['mkdir', '-p', 'packages'])
    write_string("packages/bootstrap_id.bootstrap.tar.xz", "bootstrap_contents")
    write_json("packages/bootstrap_id.active.json", ['a--b', 'c--d', 'e--f'])
    write_string("packages/bootstrap.latest", "bootstrap_id")

    return {
        None: "bootstrap_id"
    }


stable_artifacts_metadata = {
    'commit': 'commit_sha1',
    'core_artifacts': [
        {'local_path': 'packages/bootstrap_id.bootstrap.tar.xz',
            'reproducible_path': 'bootstrap/bootstrap_id.bootstrap.tar.xz'},
        {'local_path': 'packages/bootstrap_id.active.json',
            'reproducible_path': 'bootstrap/bootstrap_id.active.json'},
        {'local_path': 'packages/bootstrap.latest',
            'channel_path': 'bootstrap.latest'},
        {'local_path': 'packages/a/a--b.tar.xz',
            'reproducible_path': 'packages/a/a--b.tar.xz'},
        {'local_path': 'packages/c/c--d.tar.xz',
            'reproducible_path': 'packages/c/c--d.tar.xz'},
        {'local_path': 'packages/e/e--f.tar.xz',
            'reproducible_path': 'packages/e/e--f.tar.xz'}
    ],
    'packages': ['a--b', 'c--d', 'e--f'],
    'bootstrap_dict': {None: "bootstrap_id"}}


# TODO(cmaloney): Add test for do_build_packages returning multiple bootstraps
# containing overlapping
def test_make_stable_artifacts(monkeypatch, tmpdir):
    monkeypatch.setattr("providers.release.do_build_packages", mock_do_build_packages)
    monkeypatch.setattr("providers.util.dcos_image_commit", "commit_sha1")

    with tmpdir.as_cwd():
        metadata = release.make_stable_artifacts("http://test", False)
        assert metadata == stable_artifacts_metadata


# NOTE: Implicitly tests all providers do_create functions since it calls them.
# TODO(cmaloney): Test make_channel_artifacts, module do_create functions
def mock_build_genconfs(bootstrap_dict, repo_channel_path):
    return {
        None: ('genconf-id', 'dcos_generate_config.sh'),
        'ee': ('genconf-id-ee', 'dcos_generate_config.ee.sh')
    }


# Test that the do_create functions for each provider output data in the right
# shape.
def test_make_channel_artifacts(monkeypatch):
    write_string_args = []
    monkeypatch.setattr('pkgpanda.util.write_string', lambda *args: write_string_args.append(args))
    monkeypatch.setattr('providers.release.build_genconfs', mock_build_genconfs)

    metadata = {
        'commit': 'sha-1',
        'tag': 'test_tag',
        'bootstrap_dict': {
            None: 'bootstrap_id',
            'ee': 'ee_bootstrap_id'
        },
        'repo_channel_path': 'r_path/channel',
        'channel_commit_path': 'r_path/channel/commit/sha-1',
        'repository_path': 'r_path',
        'storage_urls': {
            'aws': 'https://aws.example.com/',
            'azure': 'https://azure.example.com/'
        },
        'repository_url': 'https://aws.example.com/r_path'
    }

    channel_artifacts = release.make_channel_artifacts(metadata)

    # Validate the artifacts are vaguely useful
    for artifact in channel_artifacts:
        assert 'local_path' in artifact or 'local_content' in artifact
        assert 'reproducible_path' in artifact or 'channel_path' in artifact

    assert write_string_args == [
        ('docker-tag', 'genconf-id'),
        ('docker-tag.txt', 'genconf-id')
    ]


def test_make_abs():
    assert release.make_abs("/foo") == '/foo'
    assert release.make_abs("foo") == os.getcwd() + '/foo'


def test_do_variable_set_or_exists(monkeypatch, tmpdir):
    with pytest.raises(SystemExit):
        release.do_variable_set_or_exists("NOT_SET_ENV_VARIABLE", "/non/existent/filename")

    # Unset environment variable
    assert release.do_variable_set_or_exists("NOT_SET_ENV_VARIABLE", str(tmpdir)) == str(tmpdir)

    # Set env var to directory that exists, directory passed which doesn't exist
    monkeypatch.setenv("magic_test_environment_variable", str(tmpdir))
    assert release.do_variable_set_or_exists("magic_test_environment_variable", "/non/existent/filename") == str(tmpdir)

    # Set env var to directory that exists, directory passed which exists
    subdir = tmpdir.mkdir("tmp_2")
    assert release.do_variable_set_or_exists("magic_test_environment_variable", str(subdir)) == str(tmpdir)

    # Set env var to directory that doesn't exist, directory passed which exists
    monkeypatch.setenv("magic_test_environment_variable", "/non/existent/filename")
    with pytest.raises(SystemExit):
        release.do_variable_set_or_exists("magic_test_environment_variable", str(tmpdir))


# TODO(cmaloney): Test do_build_packages?

# TODO(cmaloney): Test make_genconf_docker

# TODO(cmaloney): Test build_genconfs

# TODO(cmaloney): Test ReleaseManager
