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

    cluster_config = config['cluster_config']
    ssh_config = config['ssh_config']

    dep_tree = {
        "cluster_config": {
            "master_list": helpers.validate_ip_list('master_list', cluster_config),
            "exhibitor_zk_hosts": helpers.validate_string('exhibitor_zk_hosts', cluster_config),
            "cluster_name": helpers.validate_string('cluster_name', cluster_config),
            "resolvers": helpers.validate_ip_list('resolvers', cluster_config),
            "master_list": helpers.validate_ip_list('master_list', cluster_config),
            "ip_detect_path": helpers.validate_path('ip_detect_path', cluster_config),
        },
        "ssh_config": {
            "ssh_port": helpers.validate_int('ssh_port', ssh_config),
            "ssh_key_path": helpers.validate_path('ssh_key_path', ssh_config),
            "ssh_user": helpers.validate_string('ssh_user', ssh_config),
            "target_hosts": helpers.validate_ip_list('target_hosts', ssh_config),
        }
    }

    # For each dependency, read its validation helper func and return
    for tk, tv in dep_tree.items():
        for rk, rv in tv.items():
            if rv[0]:
                log.debug("%s: %s", rk, rv[1])
                messages['success'][rk] = '{}'.format(rv[1])

            else:
                log.error("%s: %s", rk, rv[1])
                messages['errors'][rk] = '{}'.format(rv[1])

    return messages
