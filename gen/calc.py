import json
import logging as log
import os
import sys
from math import floor
from subprocess import check_output

import yaml

import gen.aws.calc
import gen.azure.calc
import pkgpanda.exceptions
from pkgpanda import PackageId
from pkgpanda.build import hash_checkout


def calculate_is_ee():
    variant = os.getenv('BOOTSTRAP_VARIANT')
    return 'true' if variant == 'ee' else 'false'


def calulate_dcos_image_commit():
    dcos_image_commit = os.getenv('DCOS_IMAGE_COMMIT', None)

    if dcos_image_commit is None:
        dcos_image_commit = check_output(['git', 'rev-parse', 'HEAD']).decode('utf-8').strip()

    if dcos_image_commit is None:
        raise "Unable to set dcos_image_commit from teamcity or git."

    return dcos_image_commit


def calculate_resolvers_str(resolvers):
    # Validation because accidentally slicing a string instead of indexing a
    # list of resolvers then finding out at cluster launch is painful.
    assert isinstance(resolvers, str)
    resolvers = json.loads(resolvers)
    assert isinstance(resolvers, list)
    return ",".join(resolvers)


def calculate_mesos_dns_resolvers_str(resolvers):
    assert isinstance(resolvers, str)
    resolver_list = json.loads(resolvers)

    # Mesos-DNS unfortunately requires completley different config parameters
    # for saying "Don't resolve / reject non-Mesos-DNS requests" than "there are
    # no upstream resolvers". As such, if resolvers is given output that.
    # Otherwise output the option externalOn which means "don't try resolving
    # external queries / just fail fast without an error."
    # This logic _should_ live in the Jinja template but it unfortunately can't
    # because the "unset argument detection" in Jinja doesn't work around using
    # jinja functions (the function names show up as unset arguments...).
    # As such, generate the full JSON line and replace it in the manner given
    # above.
    if len(resolver_list) > 0:
        return '"resolvers": ' + resolvers
    else:
        return '"externalOn": false'


def calculate_ip_detect_contents(ip_detect_filename):
    if os.path.exists(ip_detect_filename):
        return yaml.dump(open(ip_detect_filename, encoding='utf-8').read())
    else:
        log.error("Ip-detect script: %s. Does not exist.", ip_detect_filename)
        sys.exit(1)


def calculate_gen_resolvconf_search(dns_search):
    if len(dns_search) > 0:
        return "SEARCH=" + dns_search
    else:
        return ""


def validate_num_masters(num_masters):
    assert int(num_masters) in [1, 3, 5, 7, 9], "Must have 1, 3, 5, 7, or 9 masters. Found {}".format(num_masters)


def validate_bootstrap_url(bootstrap_url):
    assert len(bootstrap_url) > 1, "Must be more than one character"
    assert bootstrap_url[-1] != '/', "Must not end in a '/'"


def validate_channel_name(channel_name):
    assert len(channel_name) > 1, "Must be more than 2 characters"
    assert channel_name[0] != '/', "Must not start with a '/'"
    assert channel_name[-1] != '/', "Must not end with a '/'"


def validate_dns_search(dns_search):
    assert '\n' not in dns_search, "Newlines are not allowed"
    assert ',' not in dns_search, "Commas are not allowed"

    # resolv.conf requirements
    assert len(dns_search) < 256, "Must be less than 256 characters long"
    assert len(dns_search.split()) <= 6, "Must contain no more than 6 domains"


def validate_json_list(json_list):
    try:
        list_data = json.loads(json_list)

        assert type(list_data) is list, "Must be a JSON list. Got a {}".format(type(list_data))
    except json.JSONDecodeError as ex:
        # TODO(cmaloney):
        assert False, "Must be a valid JSON list. Errors whilewhile parsing at position {}: {}".format(ex.pos, ex.msg)


def validate_master_list(master_list):
    return validate_json_list(master_list)


def validate_mesos_dns_ip_sources(mesos_dns_ip_sources):
    return validate_json_list(mesos_dns_ip_sources)


def calc_num_masters(master_list):
    return str(len(json.loads(master_list)))


def calculate_config_id(dcos_image_commit, user_arguments, mixins):
    return hash_checkout({
        "commit": dcos_image_commit,
        "user_arguments": json.loads(user_arguments),
        "mixins": json.loads(mixins)})


def calculate_cluster_packages(package_names, config_id):
    def get_package_id(package_name):
        pkg_id_str = "{}--setup_{}".format(package_name, config_id)
        # validate the pkg_id_str generated is a valid PackageId
        return pkg_id_str

    cluster_package_ids = list(sorted(map(get_package_id, json.loads(package_names))))
    return json.dumps(cluster_package_ids)


def validate_cluster_packages(cluster_packages):
    pkg_id_list = json.loads(cluster_packages)
    for pkg_id in pkg_id_list:
        try:
            PackageId(pkg_id)
        except pkgpanda.exceptions.ValidationError as ex:
            raise AssertionError(str(ex)) from ex


def validate_zk_hosts(exhibitor_zk_hosts):
    assert not exhibitor_zk_hosts.startswith('zk://'), "Must be of the form `host:port,host:port', not start with zk://"


def validate_zk_path(exhibitor_zk_path):
    assert exhibitor_zk_path.startswith('/'), "Must be of the form /path/to/znode"

entry = {
    'validate': [
        validate_num_masters,
        validate_bootstrap_url,
        validate_channel_name,
        validate_dns_search,
        validate_master_list,
        validate_zk_hosts,
        validate_zk_path,
        validate_cluster_packages,
        validate_mesos_dns_ip_sources],
    'default': {
        'weights': '',
        'docker_remove_delay': '1hrs',
        'gc_delay': '2days',
        'dns_search': '',
        'superuser_username': '',
        'superuser_password_hash': '',
        'mesos_dns_ip_sources': '["host", "netinfo"]'
    },
    'must': {
        'master_quorum': lambda num_masters: str(floor(int(num_masters) / 2) + 1),
        'resolvers_str': calculate_resolvers_str,
        'dcos_image_commit': calulate_dcos_image_commit,
        'ip_detect_contents': calculate_ip_detect_contents,
        'mesos_dns_resolvers_str': calculate_mesos_dns_resolvers_str,
        'dcos_version': '1.7-dev',
        'dcos_gen_resolvconf_search_str': calculate_gen_resolvconf_search,
        'curly_pound': '{#',
        'cluster_packages': calculate_cluster_packages,
        'config_id': calculate_config_id,
    },
    'conditional': {
        'master_discovery': {
            'master_http_loadbalancer': {},
            'vrrp': {},
            'static': {
                'must': {'num_masters': calc_num_masters}
            }
        },
        'provider': {
            'onprem': {
                'default': {
                    'resolvers': '["8.8.8.8", "8.8.4.4"]'
                },
                'must': {
                    'is_ee': calculate_is_ee
                }
            },
            'azure': gen.azure.calc.entry,
            'aws': gen.aws.calc.entry,
            'other': {}
        },
        'is_ee': {
            'true': {
                'must': {
                    'ui_authentication': 'true',
                    'ui_settings': 'true'
                },
                'default': {
                    'ui_tracking': 'false'
                }
            },
            'false': {
                'must': {
                    'ui_authentication': 'false',
                    'ui_settings': 'false'
                },
                'default': {
                    'ui_tracking': 'true'
                }
            }
        }
    }
}
