"""
Validation helper methods. Each helper method is accessed when the dep_tree
is rendered in .validate. In order to access this tree and execute functions
on possible None or empty key values (i.e., the key does not exist in the
configuration passed to validate), we always pass the func the key to validate
and the complete config dictionary passed to validate. This way, we can
return false and None if the key is not in the config.

This setup is required for all helpers:
def validate_something(key=None, config=None):
  if not key in config:
  ...
  else:
      return False, None

Helper methods should start with 'validate_' and methods that are helpers
to those should follow a 'is_something_..' construct as to be able to use
them in other validate methods.
"""
import logging
import os
import socket

log = logging.getLogger(__name__)


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


def validate_ip_list(key=None, config=None, optional=False):
    if key in config and key is not None:
        key = config[key]
        if type(key) == list:
            failed_ips = []
            for ip in key:
                if ip is not None:
                    if is_valid_ipv4_address(ip):
                        continue
                    else:
                        failed_ips.append(ip)

                else:
                    return [False, 'Enter a valid IPv4 address.', optional]

            if len(failed_ips) > 0:
                return [False, 'Enter a valid IPv4 address. The following are not IPv4 addresses: {}'.format(
                    failed_ips),
                    optional]

        else:
            return [False, 'IPv4 addresses must be a list'.format(key), optional]

        return [True, '{} is a valid list of IPv4 addresses.'.format(key), optional]

    return [False, None, optional]


def validate_master_list(key=None, config=None, optional=False):
    if key in config and key is not None:
        is_ip_list = validate_ip_list(key, config, optional)
        if not is_ip_list[0]:
            return is_ip_list

        # Check for IP dups
        if len(config['agent_list']) > 0:
            agent_dups = [a for a in config[key] if a in config['agent_list']]
            if len(agent_dups) > 0:
                return [
                    False,
                    'Master list must not contain IPs from agent list. Duplicates found: {}'.format(agent_dups),
                    optional]

        key = config[key]
        num_mstrs = len(key)
        if int(num_mstrs) in [1, 3, 5, 7, 9]:
            return [True, 'Master list is 1, 3, 5, 7, or 9 hosts. Found {}'.format(num_mstrs), optional]

        return [False, 'Master list must have 1, 3, 5, 7, or 9 hosts. Found {}.'.format(num_mstrs), optional]

    return [False, None, optional]


def validate_agent_list(key=None, config=None, optional=False):
    if key in config and key is not None:
        is_ip_list = validate_ip_list(key, config, optional)
        if not is_ip_list[0]:
            return is_ip_list

        # Check for IP dups
        if len(config['master_list']) > 0:
            mstr_dups = [a for a in config[key] if a in config['master_list']]
            if len(mstr_dups) > 0:
                return [
                    False,
                    'Agent list must not contain IPs from master list. Duplicates found: {}'.format(mstr_dups),
                    optional]
        return [True, 'Agent list is valid.', optional]
    return [True, None, optional]


def validate_string(key=None, config=None, optional=False):
    if key in config and key is not None:
        key = config[key]
        if type(key) == str and key != '':
            return [True, '{} is a valid string.'.format(key), optional]

        else:
            return [False, 'Enter a valid string'.format(key), optional]

    return [False, None, optional]


def validate_int(key=None, config=None, optional=False):
    if key in config and key is not None:
        key = config[key]
        if key is not None and key != '':
            if isinstance(key, int):
                return [True, '{} is a valid integer.'.format(key), optional]

            elif isinstance(key, str):
                try:
                    interger = int(key)
                    return [True, '{} is a valid interger.'.format(interger), optional]
                except:
                    return [False, '{} is not a valid integer. It is of type {}.'.format(key, str(type(key))), optional]
            else:
                return [False, '{} is not a valid integer. It is of type {}.'.format(key, str(type(key))), optional]

        return [False, 'Enter a valid integer.', optional]

    return [False, None, optional]


def validate_port(key=None, config=None, optional=False):
    if key in config and key is not None and key is not '':
        is_int = validate_int(key, config, optional)
        if not is_int[0]:
            return is_int

        key = config[key]
        if int(key) > 65535:
            return [False, "Ports must be less than or equal to 65535", optional]

        else:
            return [True, "Port is less than or equal to 65535", optional]

    return [False, 'Enter a valid port number (not greater than :65535)', optional]


def validate_install_type(key=None, config=None, optional=False):
    if key in config:
        key = config[key]
        if key in ['onprem']:
            return [True, '{} is a valid install_type.'.format(key), optional]

        else:
            return [False, '{} is not a valid install_type.'.format(key), optional]

    return [False, None, optional]


def validate_list(key=None, config=None, optional=False):
    if key in config:
        key = config[key]
        if type(key) == list:
            return [True, '{} is a valid list.'.format(key), optional]

        else:
            return [False, '{} is not a valid list.'.format(key), optional]

    return [False, None, optional]


def validate_exhibitor_zk_hosts(key=None, config=None, optional=False):
    if key in config and key is not None:
        key = config[key]
        try:
            for address in key.split(','):
                if is_valid_ipv4_address(address.split(':')[0].strip()):
                    continue
                else:
                    return [False, '{} is not a valid IPv4 address'.format(address.split(':')[0].strip()), optional]

        except:
            if key is not None and is_valid_ipv4_address(key.split(':')[0]):
                pass
            elif key is not None:
                return [False, '{} is not a valid IPv4 address'.format(key.split(':')[0].strip()), optional]

        else:
            return [True, '{} is valid exhibitor ZK hosts format.'.format(key), optional]

    return [False, 'None is not a valid Exhibitor Zookeeper host', optional]


def validate_path(key=None, config=None, optional=False):
    """
    Validate a path exists.
    """
    truncate_paths = {
        '/genconf/ip-detect': 'genconf/ip-detect',
        '/genconf/ssh_key': 'genconf/ssh_key'}
    if key in config:
        key = config[key]
        if os.path.exists(key):
            return [True, 'File exists {}'.format(key), optional]

        else:
            if key in truncate_paths.keys():
                return [False, 'File does not exist {}'.format(truncate_paths[key]), optional]
            else:
                return [False, 'File does not exist {}'.format(key), optional]

    return [False, None, optional]


def validate_master_discovery(key=None, config=None, optional=False):
    """
    Validate master discovery method.
    """
    if key in config:
        key = config[key]
        options = ['static']
        if key in options:
            return [True, 'master_discovery method is valid.', optional]

        else:
            return [False, 'master_discovery method is not valid. Valid options are {}'.format(options), optional]

    return [False, None, optional]


def validate_exhibitor_storage_backend(key=None, config=None, optional=False):
    """
    Validate master discovery method.
    """
    if key in config:
        key = config[key]
        options = ['zookeeper', 'aws_s3', 'shared_filesystem']
        if key in options:
            return [True, 'exhibitor_storage_backend is valid.', optional]

        else:
            return [False, 'exhibitor_storage_backend is not valid. Valid options are {}'.format(options), optional]

    return [False, None, optional]


def validate_comma_list(key=None, config=None):
    if key in config:
        key = config[key]
        if type(key) == str:
            if key.split(','):
                return [True, '{} is a valid comma separated list'.format(key)]
            else:
                return [True, '{} is a valid single entity string.'.format(key)]
        else:
            return [False, '{} is not a valid string. Looking for comma separated list.'.format(key)]

    return [False, None]


def validate_ssh_key(key=None, config=None, optional=False):
    if key in config:
        is_string = validate_string(key, config)
        if not is_string[0]:
            return [False, "SSH key must be an unencrypted (no passphrase) SSH key that is not empty.", optional]

        key = config[key]
        if key != '':
            # Validate the PEM encoded file
            if 'ENCRYPTED' in key:
                return [
                    False,
                    "Encrypted SSH keys (which contain passphrases) are not allowed. Use a key without a passphrase.",  # noqa
                    optional]

            else:
                return [True, 'This is a valid SSH key', optional]

        return [
            False,
            "Empty keys are not allowed. Enter a non-empty unencrypted (no passphrase) SSH key.",
            optional]

    return [False, None, optional]


def validate_ip_detect_script(key=None, config=None, optional=False):
    fm = 'Provide a valid executable script. Script must start with #!/'
    failed_validation = [False, fm, False]
    if key in config:
        is_string, msg, optional = validate_string(key, config, optional)
        if not is_string:
            return failed_validation

        key = config[key]
        if key != '':
            # Validate it's a script of some sort, i.e. #!/
            if key.startswith('#!/'):
                return [True, 'Is an executable script']
            else:
                return failed_validation

        return failed_validation

    return [False, None, False]
