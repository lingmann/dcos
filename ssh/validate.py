import getpass
import pwd
import os
import socket
import stat

import ssh.ssh_runner

OWNERSHIP_BITMASK = 0b111111


class ValidationException(Exception):
    """Validation Exception class"""


class ExecuteException(Exception):
    """Raised when commend execution fails"""


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


class ErrorsCollector():
    def __init__(self, throw_if_errors=True):
        self.errors = []
        self.throw_if_errors = throw_if_errors

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def validate(self):
        if not self.errors:
            return []
        if not self.throw_if_errors:
            return self.errors
        raise ValidationException(self.errors)

    def is_type(self, keys, cls, instance):
        '''
        Helper function to test a variable type.
        :param keys: array of strings, each string is a property in cls
        :param cls: self instance of ssh_runner class, will be used to find keys with getattr()
        :param instance: type of object to test
        '''
        for key in keys:
            check_value = getattr(cls, key)
            if not isinstance(check_value, instance):
                self.errors.append('{} must be {}'.format(key, instance.__name__))

    def is_not_none(self, cls, keys):
        '''
        Test if variable is not None
        :param cls: self instance of ssh_runner class, will be used to find keys with getattr()
        :param keys: array of strings, each string is a property in cls
        '''
        for key in keys:
            check_value = getattr(cls, key)
            if check_value is None:
                self.errors.append('{} must not be None'.format(key))

    def is_string(self, cls, keys):
        '''
        Test if variable is String
        :param cls: self instance of ssh_runner class, will be used to find keys with getattr()
        :param keys: array of strings, each string is a property in cls
        '''
        self.is_type(keys, cls, str)

    def is_int(self, cls, keys):
        '''
        Test if variable is not Integer
        :param cls: self instance of ssh_runner class, will be used to find keys with getattr()
        :param keys: array of strings, each string is a property in cls
        '''
        self.is_type(keys, cls, int)

    def is_list_not_empty(self, cls, keys):
        '''
        Test if variable keys are not an empty dict
        :param cls: self instance of ssh_runner class, will be used to find keys with getattr()
        :param keys: array of strings, each string is a property in cls
        '''
        for key in keys:
            check_value = getattr(cls, key)
            if not check_value:
                self.errors.append('{} list should not be empty'.format(key))

    def is_file(self, cls, keys):
        '''
        Test if keys are valid file
        :param cls: self instance of ssh_runner class, will be used to find keys with getattr()
        :param keys: array of strings, each string is a property in cls
        '''
        for key in keys:
            check_value = getattr(cls, key)
            error_msg = '{} file {} does not exist on filesystem'
            try:
                if not os.path.isfile(check_value):
                    self.errors.append(error_msg.format(key, check_value))
            except TypeError:
                self.errors.append(error_msg.format(key, check_value))

    def is_dir(self, cls, keys):
        '''
        Test if keys are valid directory
        :param cls: self instance of ssh_runner class, will be used to find keys with getattr()
        :param keys: array of strings, each string is a property in cls
        '''
        for key in keys:
            check_value = getattr(cls, key)
            error_msg = '{} directory {} does not exist on filesystem'
            try:
                if not os.path.isdir(check_value):
                    self.errors.append(error_msg.format(key, check_value))
            except TypeError:
                self.errors.append(error_msg.format(key, check_value))

    def is_valid_ip(self, cls, keys):
        '''
        Test if keys are valid IPv4 address
        :param cls: self instance of ssh_runner class, will be used to find keys with getattr()
        :param keys: array of strings, each string is a property in cls
        '''
        for key in keys:
            for ip in getattr(cls, key):
                ip = ssh.ssh_runner.parse_ip(ip)['ip']
                if not is_valid_ipv4_address(ip):
                    self.errors.append('{} is not a valid IPv4 address, field: {}'.format(ip, key))
                    # cmaloney: I think we should actually hard-error on IPv6 addresses, at this point in time
                    # (And for the forseeable future) Mesos is IPv4 only, and some of our software falls apart in
                    # dual-stack environments (Although more of it works now than it used to).

    def is_valid_private_key_permission(self, cls, keys, ssh_key_owner=None):
        '''
        Test if keys have valid provate key ownership and permission
        :param cls: self instance of ssh_runner class, will be used to find keys with getattr()
        :param keys: array of strings, each string is a property in cls
        :param ssh_key_owner: assume default key owner is a current user, unless this parameter is specified
        '''
        if ssh_key_owner is None:
            ssh_key_owner = getpass.getuser()

        for key in keys:
            check_value = getattr(cls, key)
            try:
                uid = os.stat(check_value).st_uid
            except FileNotFoundError:
                self.errors.append('No such file or directory: {}'.format(check_value))
                continue
            except TypeError:
                self.errors.append('Cannot specify {} for path argument'.format(check_value))
                continue

            user = pwd.getpwuid(uid).pw_name
            if ssh_key_owner != user:
                self.errors.append('{} owner should be {}, field: {}'.format(check_value, ssh_key_owner, key))

            # OWNERSHIP_BITMASK is used to check that only owner permissions set
            if os.stat(check_value).st_mode & OWNERSHIP_BITMASK > 0:
                oct_permissions = oct(os.stat(check_value)[stat.ST_MODE])[-4:]
                self.errors.append('permissions {} for {} are too open'.format(oct_permissions, check_value))
