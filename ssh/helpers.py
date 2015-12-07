"""
Helper functions for the SSH library.
"""
import time
import os
import yaml


def get_structured_results(command_result):
    """
    Takes the output from a SSH run and returns structured output for the
    log file.
    """
    host = command_result['host']['ip']
    timestamp = time.strftime("%Y%m%d-%H%M%S")

    return {
        host: {
            timestamp: command_result
        }
    }


def dump_host_results(log_directory, host, results, log_type='preflight'):
    """
    Dumps the results to our preflight log file. Assumes incoming results are already
    pre-structured.
    """
    log_file = '{}/{}_{}.log'.format(log_directory, host, log_type)
    if os.path.exists(log_file):
        current_file = yaml.load(open(log_file))
        for fhost, data in current_file.items():
            if host == fhost:
                for timestamp, values in data.items():
                    results[fhost][timestamp] = values

            else:
                results[fhost] = data

    with open(log_file, 'w') as preflight_file:
        preflight_file.write(yaml.dump(results, default_flow_style=False))
