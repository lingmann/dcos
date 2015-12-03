import json
import logging as log
import os
import sys
import urllib.request
from math import floor
from subprocess import check_output

import yaml


def calulate_dcos_image_commit(arguments):
    dcos_image_commit = os.getenv('DCOS_IMAGE_COMMIT', None)

    if dcos_image_commit is None:
        dcos_image_commit = check_output(['git', 'rev-parse', 'HEAD']).decode('utf-8').strip()

    if dcos_image_commit is None:
        raise "Unable to set dcos_image_commit from teamcity or git."

    return dcos_image_commit


def calculate_bootstrap_url(arguments):
    return "https://downloads.mesosphere.com/dcos/" + arguments['channel_name']


def calculate_bootstrap_id(arguments):
    # NOTE: We always use our repository for figuring out the current
    # bootstrap_id because it has all the bootstraps. For on-prem customers who
    # change the bootstrap_url to point to a local cluster, they still need
    # to be shipped our canoncial bootstrap for the selected release.
    url = 'https://downloads.mesosphere.com/dcos/{}/bootstrap.latest'.format(arguments['channel_name'])
    return urllib.request.urlopen(url).read().decode('utf-8')


def calculate_resolvers_str(arguments):
    # Validation because accidentally slicing a string instead of indexing a
    # list of resolvers then finding out at cluster launch is painful.
    assert isinstance(arguments['resolvers'], str)
    resolvers = json.loads(arguments['resolvers'])
    assert isinstance(resolvers, list)
    return ",".join(resolvers)


def calculate_mesos_dns_resolvers_str(arguments):
    assert isinstance(arguments['resolvers'], str)
    resolvers = json.loads(arguments['resolvers'])

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
    if len(resolvers) > 0:
        return '"resolvers": ' + arguments['resolvers']
    else:
        return '"externalOn": false'


def calculate_ip_detect_contents(arguments):
    if os.path.exists(arguments['ip_detect_filename']):
        return yaml.dump(open(arguments['ip_detect_filename'], encoding='utf-8').read())
    else:
        log.error("Ip-detect script: %s. Does not exist.", arguments['ip_detect_filename'])
        sys.exit(1)


def calculate_gen_resolvconf_search(arguments):
    if len(arguments['dns_search']) > 0:
        return "SEARCH=" + arguments['dns_search']
    else:
        return ""

must = {
    'master_quorum': lambda arguments: str(floor(int(arguments['num_masters']) / 2) + 1),
    'resolvers_str': calculate_resolvers_str,
    'dcos_image_commit': calulate_dcos_image_commit,
    'ip_detect_contents': calculate_ip_detect_contents,
    'mesos_dns_resolvers_str': calculate_mesos_dns_resolvers_str,
    'dcos_version': lambda arguments: "1.5",
    'dcos_gen_resolvconf_search_str': calculate_gen_resolvconf_search
}

can = {
    'bootstrap_url': calculate_bootstrap_url,
    'bootstrap_id': calculate_bootstrap_id
}


def validate(arguments):
    assert(int(arguments['num_masters']) in [1, 3, 5, 7, 9])

    assert arguments['bootstrap_url'][-1] != '/'

    if len(arguments['channel_name']):
        assert arguments['channel_name'][0] != '/'
        assert arguments['channel_name'][-1] != '/'

    assert '\n' not in arguments['dns_search']
    assert ',' not in arguments['dns_search']

    # TODO(cmaloney): Check dns_search:
    #   - is < 256 characters
    #   - Contains at most 6 search domains
    #   - Each search domain is space separated

defaults = {
    "num_masters": "3",
    "channel_name": "testing/continuous",
    "roles": "slave_public",
    "weights": "slave_public=1",
    "docker_remove_delay": "1hrs",
    "gc_delay": "2days",
    "dns_search": ""
}

parameters = ["channel_name", "dns_search", "ip_detect_filename", "resolvers"]

implies = {
    "master_discovery": {
        "cloud_dynamic": None,
        "static": "dns-master-list",
        "vrrp": "onprem-keepalived"
    }
}
