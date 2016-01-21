import os
import yaml

from dcos_installer import backend

config_path = '/tmp/config.yaml'


def test_good_create_config_from_post():
    """
    Test that it creates the config
    """
    config_path = '/tmp/config.yaml'
    good_post_data = {
        "agent_list": ["10.0.0.2"],
        "master_list": ["10.0.0.1"],
        "cluster_name": "Good Test",
        "resolvers": ["4.4.4.4"],
    }
    expected_good_messages = {}

    err, msg = backend.create_config_from_post(
        post_data=good_post_data,
        config_path=config_path)

    assert err is False
    assert msg == expected_good_messages
    os.remove(config_path)


def test_bad_create_config_from_post():
    config_path = '/tmp/config.yaml'
    bad_post_data = {
        "agent_list": "",
        "master_list": "",
        "resolvers": "",
    }
    expected_bad_messages = {
        "agent_list": " is not of type list.",
        "master_list": " is not of type list.",
        "resolvers": " is not of type list."
    }
    err, msg = backend.create_config_from_post(
        post_data=bad_post_data,
        config_path=config_path)
    assert err is True
    assert msg == expected_bad_messages
    os.remove(config_path)


def test_get_config():
    expected_file = """
---
agent_list:
- null
cluster_name: 'Mesosphere: The Data Center Operating System'
exhibitor_zk_hosts: null
extra_ssh_options: -tt
ip_detect_path: /genconf/ip-detect
log_directory: /genconf/logs
master_list:
- null
process_timeout: 120
resolvers:
- 8.8.8.8
- 8.8.4.4
ssh_key_path: /genconf/ssh_key
ssh_port: 22
ssh_user: centos
    """
    config = backend.get_config(config_path='/tmp/config.yaml')
    expected_config = yaml.load(expected_file)
    assert expected_config == config
    os.remove(config_path)


def test_return_configure_status():
    """
    This entire method will change with the new validation lib, passing
    until we have an implementation.
    """
#    msg = backend.return_configure_status(config_path=config_path)
#    expected_msg = {
#        'success': {
#            'cluster_name': 'Mesosphere: The Data Center Operating System is a valid string.',
#            'ssh_user': 'centos is a valid string.',
#            'resolvers': "['8.8.8.8', '8.8.4.4'] is a valid list of IPv4 addresses.",
#            'ip_detect_path': 'File exists /genconf/ip-detect',
#            'ssh_port': '22 is a valid integer.'},
#        'errors': {
#            'ssh_key_path': 'File does not exist /genconf/ssh_key',
#            'agent_list': '[None] is not valid IPv4 address.',
#            'master_list': '[None] is not valid IPv4 address.',
#            'exhibitor_zk_hosts': "None is not a valid string. Is of type <class 'NoneType'>."},
#        'warning': {}}
#    assert expected_msg == msg
#    os.remove(config_path)
    pass


def test_determine_config_type():
    got_output = backend.determine_config_type(config_path=config_path)
    expected_output = {
        'message': '',
        'type': 'minimal',
    }
    assert got_output == expected_output
    os.remove(config_path)


def test_success():
    got_output = backend.success(config_path=config_path)
    expected_output = {
        "success": "http://None",
        "master_count": 0,
        "agent_count": 0
    }
    assert got_output == expected_output
    os.remove(config_path)
