#!/usr/bin/env python3
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


ENDPOINTS = ['metadata', 'dcos-metadata/dcos-version.json']

EVENT_NAME = 'Cluster summary'


def get_mesos_state_statistics():
    logging.info("Getting state-summary")
    state_summary = requests.get("http://leader.mesos/mesos/master/state-summary").json()

    # Summary state-summary into the pure base statistics which don't contain possibly customer
    # sensitive data (counts of frameworks, slaves, framework names, etc.)
    return {
        'hostname': state_summary['hostname'],
        'num_frameworks': len(state_summary['frameworks']),
        'num_slaves': len(state_summary['slaves']),
        'cluster_name': state_summary['cluster'],
        'frameworks': [f.get('name') for f in state_summary['frameworks']]
    }


def read_env():
    # TODO(mj): These keys should be less tied to AWS.
    env_vars = ['AWS_REGION', 'AWS_STACK_ID', 'AWS_STACK_NAME', 'EXTERNAL_ELB']

    return {env_var: os.environ.get(env_var) for env_var in env_vars}


def report_heartbeat():
    cluster_event = get_mesos_state_statistics()

    # Augment with whitelisted environment variables
    env_vars = read_env()
    for env_var in env_vars:
        cluster_event[env_var] = env_vars[env_var]

    # Augment with cluster metadata endpoints
    for endpoint in ENDPOINTS:
        cluster_event.update(requests.get('http://leader.mesos/{}'.format(endpoint)).json())

    logging.info("Submitting to analytics")
    analytics.track(anonymous_id=uuid.uuid4().hex,
                    event=EVENT_NAME,
                    properties=cluster_event
                    )

    analytics.flush()
    logging.info("Anlytics flushed")


def main():
    args = docopt.docopt(__doc__,
                         version='0.1')

    analytics.write_key = args['--write_key']

    try:
        # if there is no leading master no-op
        subprocess.check_output(['ping', '-c1', 'leader.mesos'])
    except subprocess.CalledProcessError as ex:
        logging.info("Couldn't ping mesos master. %s", ex.output)
        sys.exit(0)

    return report_heartbeat()


if __name__ == '__main__':
    main()
