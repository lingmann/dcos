# External helpers for project-wide validation. These helpers
# are meant to be used outside of the helpers.validate funcs which
# serve validating a dependency tree. On the other hand, these
# are desigend to be use anywhere, and simply accept a key and
# return bool and message.
import os
import socket


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


def is_ip_list(key):
    if type(key) == list:
        for ip in key:
            if is_valid_ipv4_address(ip):
                continue

            else:
                return [False, '{} is not valid IPv4 address.'.format(key)]
    else:
        return [False, '{} is not of type list.'.format(key)]

    return [True, '{} is a valid list of IPv4 addresses.'.format(key)]


def is_string(key):
    if type(key) == str:
        return [True, '{} is a valid string.'.format(key)]
    else:
        return [False, '{} is not a valid string. Is of type {}.'.format(key, type(key))]


def is_integer(key):
    if type(key) == int:
        return [True, '{} is a valid integer.'.format(key)]

    else:
        return [False, '{} is not a valid integer. Is of type {}.'.format(key, type(key))]


def is_list(key):
    if type(key) == list:
        return [True, '{} is a valid list.'.format(key)]

    else:
        return [False, '{} is not a valid list.'.format(key)]


def is_path_exists(key):
    """
    Validate a path exists.
    """
    if os.path.exists(key):
        return [True, 'File exists {}'.format(key)]

    else:
        return [False, 'File does not exist {}'.format(key)]
