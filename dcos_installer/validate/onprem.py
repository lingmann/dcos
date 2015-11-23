# Dependencies for DCOS installations. Functions in this library are intended to accept a given 
# set of configuration, and returns a boolean plus a dict of values (if any) that are missing 
# for the given set of config.
from dcos_installer.log import DCOSLog
log = DCOSLog(__name__).log

from dcos_installer.validate import helpers

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
        "master_discovery": {
            "static": {
                "master_list": helpers.validate_ip_list('master_list', config),
            },
            "keepalived": {
                "keepalived_router_id": helpers.validate_int('keepalived_router_id', config),
                "keepalived_interface": str,
                "keepalived_pass": str,
                "keepalived_virtual_ipaddress": str
            },
            "cloud_dynamic": {
                "num_masters": int
            }
        },
        "exhibitor_storage_backend": {
            "zookeeper": {
                "exhibitor_zk_hosts": helpers.validate_ip_list('exhibitor_zk_hosts', config),
                "exhibitor_zk_path": helpers.validate_string('exhibitor_zk_path', config), 
            },
            "shared_filesystem": {
                "exhibitor_fs_config_dir": helpers.validate_string('exhibitor_fs_config_dir', config), 
            },
            "aws_s3": {
                "aws_access_key_id": str,
                "aws_secret_access_key": str,   
                "aws_region": str, 
                "s3_bucket": str, 
                "s3_prefix": str
            }
        }, 
        "cluster_name": helpers.validate_string('cluster_name', config), 
        "resolvers": helpers.validate_ip_list('resolvers', config),
        "weights": helpers.validate_string('weights', config),
        "bootstrap_url": helpers.validate_string('bootstrap_url', config),
        "roles": helpers.validate_string('roles', config),
        "docker_remove_delay": helpers.validate_string('docker_remove_delay', config),
        "gc_delay": helpers.validate_string('docker_remove_delay', config),
        "ssh_port": helpers.validate_int('ssh_port', config),
        "ssh_key_path": helpers.validate_path('ssh_key_path', config),
        "ssh_user": helpers.validate_string('ssh_user', config),
        "master_list": helpers.validate_ip_list('master_list', config),
        "agent_list": helpers.validate_ip_list('agent_list', config),
        "ip_detect_path": helpers.validate_path('ip_detect_path', config),
    }

            

    # For each dependency, read its validation helper func and return 

    for rk, rv in dep_tree.items():
        # All first level dep_tree items are required
        # Here we access the level 1 vars in the dep tree.
        if not rk in config:
            log.error("%s: required parameter missing.", rk)
            messages['errors'][rk] = 'Required parameter missing.'

        else:
            log.debug("%s: required parameter found.", rk)
            messages['success'][rk] = 'Required parameter found.'
            # Test validity of value given

        if type(rv) == list:
            if rv[0]:
                log.debug("%s: %s", rk, rv[1])
                messages['success'][rk] = '{}'.format(rv[1])
            
            else:
                log.error("%s: %s", rk, rv[1])
                messages['errors'][rk] = '{}'.format(rv[1])

        if type(rv) == dict:
            # Ensure the value in the config for the parameter is actually available
            # Here we access level 2 of the dep_tree, ensuring the variable passed is 
            # one of the options in the level 2 tree.
            # In other words, layer 2 items just need to be one of the options in
            # layer 2 of the dep_tree:
            try:
                if config[rk] in rv:
                    log.debug("%s: is a valid entry for %s", config[rk], rk)
                    messages['success'][config[rk]] = 'Is a valid entry for {}.'.format(rk)
                    
                    for rk2, rv2 in rv[config[rk]].items():
                        # If the child of required key (rk) is present in the config, test
                        # for it's value (the helper func). If it's not present, throw an 
                        # error to messages[errors].
                        if not rk2 in config:
                            log.debug("%s: required for %s type %s and is not present.", rk2, rk, config[rk])
                            messages['errors'][rk2] = 'Required for {} type {} and is not present.'.format(rk, config[rk])

                        else: 
                            # Test the value of required key and dump that to the messages log. 
                            # Since all helpers return a known array of [Bool, 'Message'] we 
                            # can test on [0] to validate our return.
                            if rv2[0]:
                                log.debug("%s: %s", rk2, rv2[1])
                                messages['success'][rk2] = '{}'.format(rv2[1])

                            else:
                                log.error("%s: %s", rk2, rv2[1])
                                messages['errors'][rk2] = '{}'.format(rv2[1])

                else:
                    # If the level 2 key isn't present in the dep_tree, dump the error. 
                    log.error("%s: is not a valid entry for %s.", config[rk], rk)
                    messages['errors'][config[rk]] = 'Is not a valid entry for {}.'.format(rk)
                
            except KeyError as e:
                log.error("%s: is missing a valid value.", e.args[0])
                messages['errors'][e.args[0]] = 'Is missing a valid value.'
                pass 

    return messages
