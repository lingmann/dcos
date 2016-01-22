import json
import logging as log
import os
import sys
from math import floor
from subprocess import check_output

import yaml


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

must = {
    'master_quorum': lambda num_masters: str(floor(int(num_masters) / 2) + 1),
    'resolvers_str': calculate_resolvers_str,
    'dcos_image_commit': calulate_dcos_image_commit,
    'ip_detect_contents': calculate_ip_detect_contents,
    'mesos_dns_resolvers_str': calculate_mesos_dns_resolvers_str,
    'dcos_version': lambda: "1.6",
    'dcos_gen_resolvconf_search_str': calculate_gen_resolvconf_search,
    'curly_pound': lambda: "{#"
}


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


validate = [
    validate_num_masters,
    validate_bootstrap_url,
    validate_channel_name,
    validate_dns_search
]

defaults = {
    "num_masters": "3",
    "channel_name": "testing/continuous",
    "roles": "slave_public",
    "weights": "slave_public=1",
    "docker_remove_delay": "1hrs",
    "gc_delay": "2days",
    "dns_search": ""
}

implies = {
    "master_discovery": {
        "cloud_dynamic": None,
        "static": "dns-master-list",
        "vrrp": "onprem-keepalived"
    }
}
