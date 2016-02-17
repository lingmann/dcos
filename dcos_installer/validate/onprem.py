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
        "master_list": helpers.validate_master_list('master_list', config),
        "exhibitor_zk_hosts": helpers.validate_exhibitor_zk_hosts('exhibitor_zk_hosts', config, optional=True),
        "cluster_name": helpers.validate_string('cluster_name', config),
        "resolvers": helpers.validate_ip_list('resolvers', config, optional=True),
        "ssh_port": helpers.validate_port('ssh_port', config, optional=True),
        "ssh_user": helpers.validate_string('ssh_user', config, optional=True),
        "agent_list": helpers.validate_ip_list('agent_list', config, optional=True),
        "ip_detect_path": helpers.validate_path('ip_detect_path', config),
        "ip_detect_script": helpers.validate_ip_detect_script('ip_detect_script', config),
        "ssh_key": helpers.validate_ssh_key('ssh_key', config, optional=True),
        "ssh_key_path": helpers.validate_path('ssh_key_path', config, optional=True),
        "superuser_username": helpers.validate_string('superuser_username', config, optional=True),
        "superuser_password_hash": helpers.validate_string('superuser_password_hash', config, optional=True),
        "exhibitor_storage_backend": helpers.validate_exhibitor_storage_backend(
            'exhibitor_storage_backend',
            config,
            optional=True)}

    # For each dependency, read its validation helper func and return
    for tk, tv in dep_tree.items():
        # Optional config returns warnings
        if len(tv) == 3 and tv[2]:
            # If the parameter is optional, warn on err but add to success if not failed
            if tv[0]:
                log.debug("%s: %s", tk, tv[1])
                messages['success'][tk] = '{}'.format(tv[1])

            else:
                log.info("UI / SSH Specific Config Warning - Ignore if you're not using SSH or web UI functionality")
                log.info("%s: %s", tk, tv[1])
                messages['warning'][tk] = '{}'.format(tv[1])

        elif tv[0]:
            log.debug("%s: %s", tk, tv[1])
            messages['success'][tk] = '{}'.format(tv[1])

        else:
            log.error("%s: %s", tk, tv[1])
            messages['errors'][tk] = '{}'.format(tv[1])

    return messages
