#!/usr/bin/env python
"""
USAGE:
    dcos_signal --write_key=<write_key>
"""


import analytics
import docopt
import os
import requests
import uuid


MASTER_LOCATION = "leader.mesos"
ENDPOINT = "/mesos/master/state-summary"

EVENT_NAME = 'Cluster summary'


def get_state_summary():
    summary_url = "http://%s%s" % (MASTER_LOCATION, ENDPOINT)
    response = requests.get(summary_url)
    return response.json()


def get_cluster_summary_event_from_json(summary_json):
    hostname = summary_json['hostname']
    num_frameworks = len(summary_json['frameworks'])
    num_slaves = len(summary_json['slaves'])
    cluster_name = summary_json['cluster']
    frameworks = summary_json['frameworks']
    frameworks_names_only = [f.get('name') for f in frameworks]

    result_dict = {'hostname': hostname,
                   'num_frameworks': num_frameworks,
                   'num_slaves': num_slaves,
                   'frameworks': frameworks_names_only,
                   'cluster_name': cluster_name}

    for framework in frameworks_names_only:
        key = "has_framework_%s" % framework
        result_dict[key] = True

    return result_dict


def read_env():
    # TODO(mj): These keys should be less tied to AWS.
    env_vars = ['AWS_REGION', 'AWS_STACK_ID', 'AWS_STACK_NAME', 'EXTERNAL_ELB']

    return {env_var: os.environ.get(env_var) for env_var in env_vars}


def report_heartbeat():
    summary_json = get_state_summary()

    cluster_event = get_cluster_summary_event_from_json(summary_json)

    env_vars = read_env()
    for env_var in env_vars:
        cluster_event[env_var] = env_vars[env_var]

    analytics.track(anonymous_id=uuid.uuid4().hex,
                    event=EVENT_NAME,
                    properties=cluster_event
                    )

    analytics.flush()


def start():
    args = docopt.docopt(__doc__,
                         version='0.1')

    analytics.write_key = args['--write_key']

    return report_heartbeat()
