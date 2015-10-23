from azure.storage._common_error import AzureMissingResourceHttpError
from unittest.mock import patch
import unittest
import release
import os


class TestAzureStorageProvider(unittest.TestCase):
    @patch('azure.storage.blob.BlobService')
    def setUp(self, mocked_blob_service):
        os.environ.update({
            'AZURE_STORAGE_ACCOUNT': 'testaccount',
            'AZURE_STORAGE_ACCESS_KEY': 'testkey'})
        self.azure = release.AzureStorageProvider('test')
        self.mocked_blob_service = mocked_blob_service

    def tearDown(self):
        self.azure = None
        self.mocked_blob_service = None

    def test_repository_url(self):
        """Validate Azure repository URL"""
        assert self.azure.repository_url == 'http://mesospheredownloads.blob.core.windows.net/dcos/test'

    def test_upload_local_file_blob_exists(self):
        """Test `upload_local_file` if blob exists"""
        self.azure.upload_local_file('/tmp/file.txt', if_not_exists=True)
        self.mocked_blob_service.assert_called_once_with(account_key='testkey', account_name='testaccount')
        self.mocked_blob_service().get_blob_properties.assert_called_once_with('dcos', 'test/tmp/file.txt')
        self.mocked_blob_service().put_block_blob_from_path.assert_not_called()

    def test_upload_local_file_blob_doesnt_exists(self):
        """Test `upload_local_file` if blob does not exist"""
        self.mocked_blob_service().get_blob_properties.side_effect = AzureMissingResourceHttpError('Mocked exception',
                                                                                                   1)
        self.azure.upload_local_file('/tmp/file.txt', if_not_exists=True)
        self.mocked_blob_service().put_block_blob_from_path.assert_called_once_with(
            'dcos', 'test/tmp/file.txt', '/tmp/file.txt', x_ms_blob_content_type=('text/plain', None))

    def test_upload_string(self):
        """Test `upload_string`"""
        args = {
            'ContentType': 'text/plain'
        }
        self.azure.upload_string('/destination_path', 'sometext', args)
        self.mocked_blob_service().put_block_blob_from_text.assert_called_once_with(
            'dcos', 'test/destination_path', b'sometext', x_ms_blob_content_type='text/plain')

    def test_copy_across(self):
        bootstrap_dict = {None: '371c8e40e15c986385a892c8253f9164a05f0d71'}
        active_packages = ['pkg1--12345', 'pkg2--12345']
        source = unittest.mock.MagicMock()
        repo_url = 'http://mesospheredownloads.blob.core.windows.net/dcos/testing/test'
        source.repository_url = repo_url
        self.azure.copy_across(source, bootstrap_dict, active_packages)
        self.mocked_blob_service().copy_blob.assert_called_with(
            'dcos', 'test/bootstrap/371c8e40e15c986385a892c8253f9164a05f0d71.active.json',
            repo_url + '/bootstrap/371c8e40e15c986385a892c8253f9164a05f0d71.active.json'
        )
        do_copy = unittest.mock.MagicMock()
        self.azure._copy_across(bootstrap_dict, active_packages, do_copy)
        assert do_copy.call_count == 4
        do_copy.assert_called_with('bootstrap/371c8e40e15c986385a892c8253f9164a05f0d71.active.json')
        do_copy.assert_any_call('bootstrap/371c8e40e15c986385a892c8253f9164a05f0d71.bootstrap.tar.xz')
        do_copy.assert_any_call('packages/pkg1/pkg1--12345.tar.xz')
        do_copy.assert_any_call('packages/pkg2/pkg2--12345.tar.xz')

    def test_put_text(self):
        self.azure.put_text('destination_path', 'sometext')
        self.mocked_blob_service().put_block_blob_from_text.assert_called_once_with(
            'dcos', 'test/destination_path', b'sometext', x_ms_blob_content_type='text/plain; charset=utf-8'
        )

    def test_put_json(self):
        self.azure.put_json('destination_path', 'sometext')
        self.mocked_blob_service().put_block_blob_from_text.assert_called_once_with(
            'dcos', 'test/destination_path', b'sometext', x_ms_blob_content_type='application/json'
        )


class TestS3StorageProvider(unittest.TestCase):
    @patch('aws_config.session_prod.resource')
    def setUp(self, mocked_s3_resource):
        os.environ.update({
            'AWS_ACCESS_KEY_ID': 'secretKeyId',
            'AWS_SECRET_ACCESS_KEY': 'secretAccessKey'
        })
        self.s3 = release.S3StorageProvider('test')
        self.mocked_s3_resource = mocked_s3_resource

    def tearDown(self):
        self.s3 = None

    def test_repository_url(self):
        """Validate S3 repository URL"""
        assert self.s3.repository_url == 'https://downloads.mesosphere.com/dcos/test'

    def test_copy_across(self):
        """Validate copy_across"""
        source = unittest.mock.MagicMock()
        bootstrap_dict = {None: '371c8e40e15c986385a892c8253f9164a05f0d71'}
        active_packages = ['pkg1--12345', 'pkg2--12345']
        self.s3.copy_across(source, bootstrap_dict, active_packages)
        assert source.get_object.call_count == 4
        source.get_object.assert_called_with('bootstrap/371c8e40e15c986385a892c8253f9164a05f0d71.active.json')
        source.get_object.assert_any_call('bootstrap/371c8e40e15c986385a892c8253f9164a05f0d71.bootstrap.tar.xz')
        source.get_object.assert_any_call('packages/pkg2/pkg2--12345.tar.xz')
        source.get_object.assert_any_call('packages/pkg1/pkg1--12345.tar.xz')

    def test_get_object(self):
        self.s3.get_object('test_object')
        self.mocked_s3_resource().Bucket().Object.assert_called_once_with('dcos/test/test_object')

    @patch('builtins.open')
    def test_upload_local_file(self, mocked_open):
        """Validate upload_local_file overwrites if file exists"""
        self.s3.upload_local_file('/tmp/test.txt')
        mocked_open.assert_called_with('/tmp/test.txt', 'rb')
        assert self.mocked_s3_resource().Bucket().Object().load.called is False
        assert self.mocked_s3_resource().Bucket().Object().put.called is True

    def test_upload_local_file_if_not_exists(self):
        """Validate upload_local_file and skip if file exists"""
        self.s3.upload_local_file('/tmp/test.txt', if_not_exists=True)
        assert self.mocked_s3_resource().Bucket().Object().load.called is True
        assert self.mocked_s3_resource().Bucket().Object().put.called is False

    @patch('pkgpanda.util')
    @patch('subprocess.check_call')
    def test_upload_string(self, mocked_check_call, mocked_pkgpanda_util):
        self.s3.upload_string('destination_path', 'some text')
        self.mocked_s3_resource().Bucket().Object().put.assert_called_with(Body=b'some text', CacheControl='no-cache')
        mocked_check_call.assert_called_with(['mkdir', '-p', 'artifacts'])
        mocked_pkgpanda_util.write_string.assert_called_with('artifacts/destination_path', 'some text')

    @patch('pkgpanda.util')
    @patch('subprocess.check_call')
    def test_put_text(self, mocked_check_call, mocked_pkgpanda_util):
        self.s3.put_text('destination_path', 'some text')
        self.mocked_s3_resource().Bucket().Object().put.assert_called_with(
            Body=b'some text', CacheControl='no-cache', ContentType='text/plain; charset=utf-8')
        mocked_check_call.assert_called_with(['mkdir', '-p', 'artifacts'])
        mocked_pkgpanda_util.write_string.assert_called_with('artifacts/destination_path', 'some text')

    @patch('pkgpanda.util')
    @patch('subprocess.check_call')
    def test_put_json(self, mocked_check_call, mocked_pkgpanda_util):
        self.s3.put_json('destination_path', 'some text')
        self.mocked_s3_resource().Bucket().Object().put.assert_called_with(
            Body=b'some text', ContentType='application/json', CacheControl='no-cache')
        mocked_check_call.assert_called_with(['mkdir', '-p', 'artifacts'])
        mocked_pkgpanda_util.write_string.assert_called_with('artifacts/destination_path', 'some text')


class TestChannelManager(unittest.TestCase):
    def setUp(self):
        self.fake_storage_provider1 = unittest.mock.MagicMock()
        self.fake_storage_provider1.name = 'aws'
        self.fake_storage_provider2 = unittest.mock.MagicMock()
        self.fake_storage_provider2.name = 'azure'
        self.cm = release.ChannelManager([self.fake_storage_provider1, self.fake_storage_provider2])

    def tearDown(self):
        self.cm = None

    def test_dispatch(self):
        self.cm.method_generated_on_the_fly(1, 2, param1=True, param2=False)
        self.fake_storage_provider1.method_generated_on_the_fly.assert_called_with(1, 2, param1=True, param2=False)
        self.fake_storage_provider2.method_generated_on_the_fly.assert_called_with(1, 2, param1=True, param2=False)

    def test_copy_across(self):
        source_fake_storage_provider1 = unittest.mock.MagicMock()
        source_fake_storage_provider1.name = 'aws'
        source_fake_storage_provider2 = unittest.mock.MagicMock()
        source_fake_storage_provider2.name = 'azure'

        source = release.ChannelManager([source_fake_storage_provider1, source_fake_storage_provider2])
        bootstrap_dict = {None: '371c8e40e15c986385a892c8253f9164a05f0d71'}
        active_packages = ['pkg1--12345', 'pkg2--12345']
        self.cm.copy_across(source, bootstrap_dict, active_packages)
        self.fake_storage_provider1.copy_across.assert_called_with(source_fake_storage_provider1,
                                                                   {None: '371c8e40e15c986385a892c8253f9164a05f0d71'},
                                                                   ['pkg1--12345', 'pkg2--12345'])
        self.fake_storage_provider2.copy_across.assert_called_with(source_fake_storage_provider2,
                                                                   {None: '371c8e40e15c986385a892c8253f9164a05f0d71'},
                                                                   ['pkg1--12345', 'pkg2--12345'])

    def test_copy_across_src_dst_providers_dont_match(self):
        source_fake_storage_provider1 = unittest.mock.MagicMock()
        source_fake_storage_provider1.name = 'aws'
        source_fake_storage_provider2 = unittest.mock.MagicMock()
        source_fake_storage_provider2.name = 'newProvider'

        source = release.ChannelManager([source_fake_storage_provider1, source_fake_storage_provider2])
        bootstrap_dict = {None: '371c8e40e15c986385a892c8253f9164a05f0d71'}
        active_packages = ['pkg1--12345', 'pkg2--12345']
        with self.assertRaises(release.CopyAcrossException):
            self.cm.copy_across(source, bootstrap_dict, active_packages)

    def test_read_file(self):
        self.cm.read_file('/tmp/test.txt')
        self.fake_storage_provider1.read_file.assert_called_with('/tmp/test.txt')
        self.fake_storage_provider2.read_file.assert_not_called()

    def test_repository_url(self):
        self.fake_storage_provider1.repository_url = 'http://aws/url'
        self.fake_storage_provider2.repository_url = 'http://azure/url'
        result_url_dict = {
            'default': 'http://aws/url',
            'aws': 'http://aws/url',
            'azure': 'http://azure/url'
        }
        assert self.cm.repository_url == result_url_dict


class TestRelease(unittest.TestCase):
    @patch('release.S3StorageProvider')
    @patch('builtins.open')
    @patch('release.ChannelManager')
    @patch('release.get_bootstrap_packages')
    @patch('subprocess.check_call')
    @patch('release.get_provider_data')
    @patch('release.do_build_packages')
    def test_do_create(self, mocked_do_build_packages, mocked_get_provider_data, mocked_check_call,
                       mocked_get_bootstrap_packages, mocked_channel_manager, mocked_open, mocked_s3):
        options = unittest.mock.MagicMock()
        options.destination_channel = 'destination'
        options.tag = 'tag'
        options.skip_upload = False
        self.fake_storage_provider1 = unittest.mock.MagicMock()
        self.fake_storage_provider1.name = 'aws'
        self.fake_storage_provider2 = unittest.mock.MagicMock()
        self.fake_storage_provider2.name = 'azure'
        mocked_do_build_packages.return_value = {None: '12345'}
        mocked_get_provider_data.return_value = ('provider_data', 'cleaned_provider_data')
        mocked_get_bootstrap_packages.return_value = set(['pkg123--12345'])
        mocked_open().read.return_value = 'test'
        release.do_create(options)
        mocked_s3.assert_called_with('testing/destination')
        mocked_channel_manager().upload_packages.assert_called_with(['pkg123--12345'])
        mocked_channel_manager().upload_bootstrap.assert_called_with({None: '12345'})
        assert mocked_check_call.call_count == 2
        assert mocked_channel_manager().upload_providers_and_activate.called is True
        mocked_open.assert_called_with('docker-tag')


if __name__ == '__main__':
    unittest.main()
