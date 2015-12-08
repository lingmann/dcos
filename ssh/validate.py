import os
import socket


class ValidationException(Exception):
    """Validation Exception class"""


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


class ErrorsCollector():
    def __init__(self, throw_if_errors=True):
        self.errors = []
        self.throw_if_errors = throw_if_errors

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def validate(self):
        if len(self.errors) < 1:
            return []
        if not self.throw_if_errors:
            return self.errors
        raise ValidationException(self.errors)

    def is_type(self, keys, cls, instance):
        for key in keys:
            check_value = getattr(cls, key)
            if not isinstance(check_value, instance):
                self.errors.append('{} must be {}'.format(key, instance.__name__))

    def is_not_none(self, cls, keys):
        for key in keys:
            check_value = getattr(cls, key)
            if check_value is None:
                self.errors.append('{} must not be None'.format(key))

    def is_string(self, cls, keys):
        self.is_type(keys, cls, str)

    def is_int(self, cls, keys):
        self.is_type(keys, cls, int)

    def is_list_not_empty(self, cls, keys):
        for key in keys:
            check_value = getattr(cls, key)
            if len(check_value) < 1:
                self.errors.append('{} list should not be empty'.format(key))

    def is_file(self, cls, keys):
        for key in keys:
            check_value = getattr(cls, key)
            error_msg = '{} file {} does not exist on filesystem'
            try:
                if not os.path.isfile(check_value):
                    self.errors.append(error_msg.format(key, check_value))
            except TypeError:
                self.errors.append(error_msg.format(key, check_value))

    def is_dir(self, cls, keys):
        for key in keys:
            check_value = getattr(cls, key)
            error_msg = '{} directory {} does not exist on filesystem'
            try:
                if not os.path.isdir(check_value):
                    self.errors.append(error_msg.format(key, check_value))
            except TypeError:
                self.errors.append(error_msg.format(key, check_value))

    def is_valid_ip(self, cls, keys):
        for key in keys:
            for ip in getattr(cls, key):
                if not is_valid_ipv4_address(ip):
                    self.errors.append('{} is not a valid IPv4 address, field: {}'.format(ip, key))
                    # cmaloney: I think we should actually hard-error on IPv6 addresses, at this point in time
                    # (And for the forseeable future) Mesos is IPv4 only, and some of our software falls apart in
                    # dual-stack environments (Although more of it works now than it used to).
                    if is_valid_ipv6_address(ip):
                        self.errors.append('{} IPv6 is currently not supported, field: {}'.format(ip, key))
