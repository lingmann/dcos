# Validation helper methods. Each helper method is accessed when the dep_tree
# is rendered in .validate. In order to access this tree and execute functions
# on possible None or empty key values (i.e., the key does not exist in the 
# configuration passed to validate), we always pass the func the key to validate
# and the complete config dictionary passed to validate. This way, we can 
# return false and None if the key is not in the config. 
#
# This setup is required for all helpers:
# def validate_something(key=None, config=None):
#   if not key in config:
#   ...
#   else:
#       return False, None
# 
# Helper methods should start with 'validate_' and methods that are helpers
# to those should follow a 'is_something_..' construct as to be able to use
# them in other validate methods. 
import socket
import os


def is_valid_ipv4_address(address):
    try:
        socket.inet_pton(socket.AF_INET, address)
    except AttributeError:  # no inet_pton here, sorry
        try:
            socket.inet_aton(address)
        except socket.error:
            return False
        return address.count('.') == 3
    except socket.error:  # not a valid address
        return False

    return True


def is_valid_ipv6_address(address):
    try:
        socket.inet_pton(socket.AF_INET6, address)
    except socket.error:  # not a valid address
        return False
    return True


def validate_ip_list(key=None, config=None):
    if key in config:
        key = config[key]
        if type(key) == list:
            for ip in key:
                if is_valid_ipv4_address(ip):
                    continue

                else:
                    return [False, '{} is not valid IPv4 address.'.format(key)]
        else:
            return [False, '{} is not of type list.'.format(key)]

        return [True, '{} is a valid list of IPv4 addresses.'.format(key)]

    return [False, None]
    

def validate_target_hosts(key=None, config=None):
    if key in config:
        key = config[key]
        if type(key) == list:
            for ip in key:
                if is_valid_ipv4_address(ip):
                    continue

                else:
                    return [False, '{} is not valid IPv4 address.'.format(key)]
        else:
            return [False, '{} is not of type list.'.format(key)]

        # Ensure the master list IPs are in the target_hosts
        if config['cluster_config']['master_list']:
            for ip in config['cluster_config']['master_list']:
                if ip in key:
                    continue

                else: 
                    return [False, '{} from master_list is not in target_hosts: {}'.format(ip, key)]

        return [True, '{} is a valid list of IPv4 addresses and contains master_list IPs'.format(key)]

    return [False, None]

 
def validate_string(key=None, config=None):
    if key in config:
        key = config[key]
        if type(key) == str:
            return [True, '{} is a valid string.'.format(key)]
        
        else:
            return [False, '{} is not a valid string. Is of type {}.'.format(key, type(key))]

    return [False, None]


def validate_int(key=None, config=None):
    if key in config:
        key = config[key]
        if type(key) == int:
            return [True, '{} is a valid integer.'.format(key)]

        else:
            return [False, '{} is not a valid integer. Is of type {}.'.format(key, type(key))]

    return [False, None]


def validate_install_type(key=None, config=None):
    if key in config:
        key = config[key]
        if key in ['onprem']:
            return [True, '{} is a valid install_type.'.format(key)]
        
        else:
            return [False, '{} is not a valid install_type.'.format(key)]

    return [False, None]


def validate_list(key=None, config=None):
    if key in config:
        key = config[key]
        if type(key) == list:
            return [True, '{} is a valid list.'.format(key)]

        else:
            return [False, '{} is not a valid list.'.format(key)]

    return [False, None]


def validate_path(key=None, config=None):
    """
    Validate a path exists. 
    """
    if key in config:
        key = config[key]
        if os.path.exists(key):
            return [True, 'File exists {}'.format(key)]

        else:
            return [False, 'File does not exist {}'.format(key)]

    return [False, None]


def validate_master_discovery(key=None, config=None):
    """
    Validate master discovery method.
    """
    if key in config:
        key = config[key]
        options = ['static']
        if key in options:
            return [True, 'master_discovery method is valid.']
        
        else:
            return [False, 'master_discovery method is not valid. Valid options are {}'.format(options)]

    return [False, None]

def validate_exhibitor_storage_backend(key=None, config=None):
    """
    Validate master discovery method.
    """
    if key in config:
        key = config[key]
        options = ['zookeeper']
        if key in options:
            return [True, 'exhibitor_storage_backend is valid.']
        
        else:
            return [False, 'exhibitor_storage_backend is not valid. Valid options are {}'.format(options)]

    return [False, None]
