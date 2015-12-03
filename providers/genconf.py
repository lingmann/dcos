#!/usr/bin/env python3
"""Generates DCOS packages and configuration."""

import argparse
import logging as log
import os
import subprocess
import sys
from argparse import RawTextHelpFormatter
from subprocess import CalledProcessError

import gen
import providers.bash as bash


def do_genconf(options):
    """
    Wraps calls to the gen library and instanciates configuration for a given provider.
    """

    # Interpolate the commands in genconf.py to gen library | i.e., set the args
    # in gen/__init__.py from our genconf.py commands
    gen_options = gen.get_options_object()
    gen_options.log_level = options.log_level
    if not options.interactive:
        gen_options.config = "/genconf/config.json"
    gen_options.output_dir = options.output_dir

    if options.interactive:
        gen_options.assume_defaults = False
        gen_options.non_interactive = False
    else:
        gen_options.assume_defaults = True
        gen_options.non_interactive = True

    subprocess.check_output(['mkdir', '-p', '/genconf/serve'])

    gen_out = do_provider(gen_options, bash, ['bash', 'centos', 'onprem'])

    # Pass the arguments from gen_out to download, specifically calling the bootstrap_id value
    fetch_bootstrap(gen_out.arguments['bootstrap_id'])


def do_provider(options, provider_module, mixins):
    # We set the channel_name, bootstrap_id in env as to not expose it to users but still make it switchable
    if 'CHANNEL_NAME' in os.environ:
        channel_name = os.environ['CHANNEL_NAME']
    else:
        log.error("CHANNEL_NAME must be set in environment to run.")
        sys.exit(1)

    if 'BOOTSTRAP_ID' in os.environ:
        bootstrap_id = os.environ['BOOTSTRAP_ID']
    else:
        log.error("BOOTSTRAP_ID must be set in environment to run.")
        sys.exit(1)

    gen_out = gen.generate(
        arguments={
            'ip_detect_filename': '/genconf/ip-detect',
            'channel_name': channel_name,
            'bootstrap_id': bootstrap_id
        },
        options=options,
        mixins=mixins,
        extra_cluster_packages=['onprem-config']
        )
    provider_module.generate(gen_out, options.output_dir)
    return gen_out


def fetch_bootstrap(bootstrap_id):
    bootstrap_filename = "{}.bootstrap.tar.xz".format(bootstrap_id)
    save_path = "/genconf/serve/bootstrap/{}".format(bootstrap_filename)

    def cleanup_and_exit():
        if os.path.exists(save_path):
            try:
                os.remove(save_path)
            except OSError as ex:
                log.error(ex.strerror)
        sys.exit(1)

    if os.path.exists(save_path):
        return

    # Check if there is an in-container copy of the bootstrap tarball, and
    # if so copy it across
    local_cache_filename = "/artifacts/" + bootstrap_filename
    assert os.path.exists(local_cache_filename)
    log.info("Copying bootstrap out of cache")
    try:
        subprocess.check_output(['mkdir', '-p', '/genconf/serve/bootstrap/'])
        subprocess.check_output(['cp', local_cache_filename, save_path])
    except (KeyboardInterrupt, CalledProcessError) as ex:
        log.error("Copy failed or interrupted %s", ex.cmd)
        log.error("Failed commandoutput: %s", ex.output)
        cleanup_and_exit()


def main():
    desc = '''Generates DCOS configuration.

Initial Setup
  1. Set up a build location for input config and artifacts (e.g.
     /dcos-config). These instructions will refer to this location as
     $BUILD_DIR.
  2. Add ip-detect script to $BUILD_DIR
  3. Add config-user.json to $BUILD_DIR (optional for interactive mode)

Interactive Mode
  1. Build DCOS artifacts:
     docker run -it -v $BUILD_DIR:/genconf dcos-genconf interactive

  All the user-input parameters will be saved to config-user-output.json. That
  file can be used as the config-user.json for either an interactive or
  non-interactive run.

Non-Interactive Mode
  1. Create an appropriate config-user.json in $BUILD_DIR
  2. Build DCOS artifacts:
     docker run -it -v $BUILD_DIR:/genconf dcos-genconf non-interactive

In both modes a file config-final.json will be output which contains all the
parameters that the input paramters were expanded to as DCOS configuration.
'''
    parser = argparse.ArgumentParser(
        description=desc, formatter_class=RawTextHelpFormatter)

    # Log level
    parser.add_argument(
        '-l',
        '--log-level',
        default='info',
        type=str,
        choices=['debug', 'info'],
        help='Log level. Info or debug')

    # Output directory
    parser.add_argument(
        '-o',
        '--output-dir',
        default='/genconf/serve',
        type=str,
        help='Output directory for genconf')

    # Set interactive mode
    parser.add_argument(
        '-i',
        '--interactive',
        action='store_true',
        default=False,
        help='Interactive configuration builder.')

    # Parse the arguments and dispatch.
    options = parser.parse_args()
    if options.log_level == "debug":
        log.basicConfig(level=log.DEBUG)
        log.debug("Log level set to DEBUG")
    elif options.log_level == "info":
        log.basicConfig(level=log.INFO)
        log.info("Log level set to INFO")
    else:
        log.error("Logging option not available: %s", options.log_level)
        sys.exit(1)

    do_genconf(options)


if __name__ == '__main__':
    main()
