import json
import subprocess

import passlib.hash

from dcos_installer import backend


def test_password_hash():
    """Tests that the password hashing method creates de-cryptable hash
    """
    password = 'DcosTestingPassword!@#'
    # only reads from STDOUT
    hash_pw = subprocess.check_output(['dcos_installer', '--hash-password', password])
    hash_pw = hash_pw.decode('ascii').strip('\n')
    assert passlib.hash.sha512_crypt.verify(password, hash_pw), 'Hash does not match password'


def test_good_create_config_from_post(tmpdir):
    """
    Test that it creates the config
    """
    # Create a temp config
    workspace = tmpdir.strpath
    temp_config_path = workspace + '/config.yaml'

    good_post_data = {
        "agent_list": ["10.0.0.2"],
        "master_list": ["10.0.0.1"],
        "cluster_name": "Good Test",
        "resolvers": ["4.4.4.4"],
    }
    expected_good_messages = {}

    err, msg = backend.create_config_from_post(
        post_data=good_post_data,
        config_path=temp_config_path)

    assert err is False
    assert msg == expected_good_messages


def test_bad_create_config_from_post(tmpdir):
    # Create a temp config
    workspace = tmpdir.strpath
    temp_config_path = workspace + '/config.yaml'

    bad_post_data = {
        "agent_list": "",
        "master_list": "",
        "resolvers": "",
    }
    expected_bad_messages = {
        "agent_list": 'IPv4 addresses must be a list',
        "master_list": 'IPv4 addresses must be a list',
        "resolvers": 'IPv4 addresses must be a list',
    }
    err, msg = backend.create_config_from_post(
        post_data=bad_post_data,
        config_path=temp_config_path)
    assert err is True
    assert msg == expected_bad_messages


def test_do_validate_config(tmpdir):
    # Create a temp config
    workspace = tmpdir.strpath
    temp_config_path = workspace + '/config.yaml'

    expected_output = {
        'errors': {
            'ip_detect_path': 'File does not exist genconf/ip-detect',
            'ip_detect_script': 'Provide a valid executable script. Script must start with #!/',
            'master_list': 'Enter a valid IPv4 address.'},
        'warning': {
            'exhibitor_zk_hosts': 'None is not a valid Exhibitor Zookeeper host',
            'ssh_key_path': 'File does not exist genconf/ssh_key',
            'ssh_key': 'SSH key must be an unencrypted (no passphrase) SSH key that is not empty.',
            'superuser_password_hash': 'Enter a valid string',
            'agent_list': 'Enter a valid IPv4 address.',
            'ssh_user': 'Enter a valid string',
            'superuser_username': 'Enter a valid string'},
        'success': {
            'exhibitor_storage_backend':
            'exhibitor_storage_backend is valid.',
            'cluster_name': 'DCOS is a valid string.',
            'resolvers': "['8.8.8.8', '8.8.4.4'] is a valid list of IPv4 addresses.",
            'ssh_port': 'Port is less than or equal to 65535'}}

    messages, return_code = backend.do_validate_config(temp_config_path)
    assert messages == expected_output


def test_get_config(tmpdir):
    # Create a temp config
    workspace = tmpdir.strpath
    temp_config_path = workspace + '/config.yaml'

    expected_file = """
{
  "superuser_username": null,
  "bootstrap_url": "file:///opt/dcos_install_tmp",
  "agent_list": [
    null
  ],
  "ssh_port": 22,
  "master_list": [
    null
  ],
  "cluster_name": "DCOS",
  "resolvers": [
    "8.8.8.8",
    "8.8.4.4"
  ],
  "superuser_password_hash": null,
  "ssh_user": null,
  "exhibitor_zk_hosts": null,
  "process_timeout": 10000,
  "exhibitor_storage_backend": "zookeeper",
  "exhibitor_zk_path": "/dcos",
  "master_discovery": "static"
}
    """
    config = backend.get_config(config_path=temp_config_path)
    expected_config = json.loads(expected_file)
    assert expected_config == config


def test_determine_config_type(tmpdir):
    # Create a temp config
    workspace = tmpdir.strpath
    temp_config_path = workspace + '/config.yaml'

    got_output = backend.determine_config_type(config_path=temp_config_path)
    expected_output = {
       'message': '',
       'type': 'minimal',
    }
    assert got_output == expected_output


def test_success(tmpdir):
    # Create a temp config
    workspace = tmpdir.strpath
    temp_config_path = workspace + '/config.yaml'

    got_output = backend.success(config_path=temp_config_path)
    expected_output = {
        "success": "http://None",
        "master_count": 0,
        "agent_count": 0
    }
    assert got_output == expected_output


def test_accept_overrides_for_undefined_config_params(tmpdir):
    temp_config_path = tmpdir.strpath + '/config.yaml'
    param = ('fake_test_param_name', 'fake_test_param_value')
    backend.create_config_from_post(
        post_data=dict([param]),
        config_path=temp_config_path)

    assert backend.get_config(config_path=temp_config_path)[param[0]] == param[1]
