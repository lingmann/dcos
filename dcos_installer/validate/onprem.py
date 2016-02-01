# Dependencies for DCOS installations. Functions in this library are intended to accept a given
# set of configuration, and returns a boolean plus a dict of values (if any) that are missing
# for the given set of config.
import logging

from dcos_installer.validate import helpers

log = logging.getLogger(__name__)


def check_dependencies(config):
    """
    Accept a dict of dependencies and return true or false and a
    dict of values (if any) of missing dependencies.
    """
    errors, validate_messages = return_data(config)

    return errors, validate_messages


def return_data(config):
    """
    Compare the configuration with the dependencies, return error, msg.
    """

    # Verify values presented are valid
    messages = get_onprem_dependencies(config)

    # Check for errors
    if len(messages['errors']) > 0:
        errors = True

    else:
        errors = False

    return errors, messages


def get_onprem_dependencies(config):
    """
    The on-prem dependency tree. Each key gets a type, provide and dependecies.
    For each type, we assert first, if it passes, we verify with provide.
    """
    # Init our return messages
    messages = {
        'errors': {},
        'success': {},
        'warning': {},
    }

    # Dependency tree: validation of the given config is done from the funcs
    # embedded in the tree. If the config isn't set we throw a KeyError, log
    # it in 'messages' and continue parsing the tree.

    dep_tree = {
        "master_list": helpers.validate_ip_list('master_list', config),
        "exhibitor_zk_hosts": helpers.validate_exhibitor_zk_hosts('exhibitor_zk_hosts', config),
        "cluster_name": helpers.validate_string('cluster_name', config),
        "resolvers": helpers.validate_ip_list('resolvers', config),
        "master_list": helpers.validate_ip_list('master_list', config),
        "ip_detect_path": helpers.validate_path('ip_detect_path', config),
        # Only validating path for script currently
        "ip_detect_script": helpers.validate_ip_detect_path('ip_detect_script', config),
        "ssh_port": helpers.validate_port('ssh_port', config),
        # Only validating path for key currently.
        "ssh_key": helpers.validate_ssh_key_path('ssh_key', config),
        "ssh_key_path": helpers.validate_path('ssh_key_path', config),
        "ssh_user": helpers.validate_string('ssh_user', config),
        "agent_list": helpers.validate_ip_list('agent_list', config),
        "superuser_username": helpers.validate_string('superuser_username', config),
        "superuser_password": helpers.validate_string('superuser_password', config),
    }

    # For each dependency, read its validation helper func and return
    for tk, tv in dep_tree.items():
        if tv[0]:
            log.debug("%s: %s", tk, tv[1])
            messages['success'][tk] = '{}'.format(tv[1])

        else:
            log.error("%s: %s", tk, tv[1])
            messages['errors'][tk] = '{}'.format(tv[1])

    return messages
