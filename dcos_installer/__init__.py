import argparse

from flask import Flask

#from fabric.api import run

#import genconf

import logging as log

import sys

from . import server

def __init__():
    """
    The web based installer leverages Flask to present end-users of 
    dcos_installer with a clean web interface to configure their
    site-based installation of DCOS.
    """
    options = parse_args()  
    set_log_level(options)
    if options.mode == 'web':
        server.run()
    else:
        log.error("Sorry, %s is not a usable run mode.", options.mode)
        sys.exit(1)

def parse_args():
    """
    Parse CLI arguments and return a map of options.
    """
    parser = argparse.ArgumentParser(description='Install DCOS on-premise')
    parser.add_argument(
        '-p', 
        '--port',
        type=int,
        default=9000,
        help='Web server port number.')

    parser.add_argument(
        '-l',
        '--log-level',
        type=str,
        default='info',
        choices=['info','debug'],
        help='Log level.')

    parser.add_argument(
        '-m',
        '--mode',
        type=str,
        choices=['non-interactive', 'interactive', 'web'],
        default='web',
        help='Installation mode.')

    parser.add_argument(
        '-c',
        '--config-path',
        type=str,
        default='dcos_config.yaml',
        help='The path to dcos_config.yaml.')

    options = parser.parse_args()
    return options


def set_log_level(options):
    """
    Given a map of options, parse for log level flag and set the 
    default logging level.
    """
    if options.log_level == "debug":
        log.basicConfig(level=log.DEBUG)
        log.debug("Log level set to DEBUG")
    elif options.log_level == "info":
        log.basicConfig(level=log.INFO)
        log.info("Log level set to INFO")
    else:
        log.error("Logging option not available: %s", options.log_level)
        sys.exit(1)

