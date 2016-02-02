import json

from dcos_installer import backend
from dcos_installer.config import DCOSConfig


def test_good_create_config_from_post(tmpdir):
    """
    Test that it creates the config
    """
    # Create a temp config
    workspace = tmpdir.strpath
    temp_config_path = workspace + '/config.yaml'

    temp_config = DCOSConfig()
    temp_config.config_path = temp_config_path
    temp_config.write()

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

    temp_config = DCOSConfig()
    temp_config.config_path = temp_config_path
    temp_config.write()

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

    temp_config = DCOSConfig()
    temp_config.config_path = temp_config_path
    temp_config.write()

    expected_output = {
        'errors': {
            'ssh_key': 'Please provide a valid RSA encoded SSH key. Key must start with -----BEGIN RSA PRIVATE KEY-----',
            'exhibitor_zk_hosts': 'None is not a valid Exhibitor Zookeeper host',
            'superuser_username': 'Please enter a valid string',
            'master_list': 'Please enter a valid IPv4 address.',
            'superuser_password_hash': 'Please enter a valid string',
            'ip_detect_path': 'File does not exist genconf/ip-detect',
            'ssh_user': 'Please enter a valid string',
            'agent_list': 'Please enter a valid IPv4 address.',
            'ssh_key_path': 'File does not exist genconf/ssh_key',
            'ip_detect_script': 'Please provide a valid executable script. Script must start with #!/'},
        'success': {
            'cluster_name': 'Mesosphere: The Data Center Operating System is a valid string.',
            'ssh_port': 'Port is less than or equal to 65535',
            'resolvers': "['8.8.8.8', '8.8.4.4'] is a valid list of IPv4 addresses."},
        'warning': {}}
    messages = backend.do_validate_config(temp_config_path)
    assert messages == expected_output


def test_get_config(tmpdir):
    # Create a temp config
    workspace = tmpdir.strpath
    temp_config_path = workspace + '/config.yaml'

    temp_config = DCOSConfig()
    temp_config.config_path = temp_config_path
    temp_config.write()

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
  "cluster_name": "Mesosphere: The Data Center Operating System",
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

    temp_config = DCOSConfig()
    temp_config.config_path = temp_config_path
    temp_config.write()

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

    temp_config = DCOSConfig()
    temp_config.config_path = temp_config_path
    temp_config.write()

    got_output = backend.success(config_path=temp_config_path)
    expected_output = {
        "success": "http://None",
        "master_count": 0,
        "agent_count": 0
    }
    assert got_output == expected_output
