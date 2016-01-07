#!/usr/bin/env python
"""
USAGE:
    dcos_signal --write_key=<write_key>
"""


import analytics
import docopt
import logging
import os
import requests
import subprocess
import sys
import uuid


MASTER_LOCATION = "leader.mesos"
ENDPOINTS = ['/mesos/master/state-summary', '/metadata']

EVENT_NAME = 'Cluster summary'


def get_state_summary():
    logging.info("Getting state-summary")
    result = {}
    for endpoint in ENDPOINTS:
        summary_url = "http://%s%s" % (MASTER_LOCATION, endpoint)
        response = requests.get(summary_url)
        result.update(response.json())
    return result


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

    logging.info("Submitting to analytics")
    analytics.track(anonymous_id=uuid.uuid4().hex,
                    event=EVENT_NAME,
                    properties=cluster_event
                    )

    analytics.flush()
    logging.info("Anlytics flushed")


def start():
    args = docopt.docopt(__doc__,
                         version='0.1')

    analytics.write_key = args['--write_key']

    try:
        # if there is no leading master no-op
        subprocess.check_output(['ping', '-c1', MASTER_LOCATION])
    except subprocess.CalledProcessError as ex:
        logging.info("Couldn't ping mesos master. %s", ex.output)
        sys.exit(0)

    return report_heartbeat()
