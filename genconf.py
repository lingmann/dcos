#!/usr/bin/env python3
"""Generates DCOS packages and configuration."""

import argparse
import glob
import json
import os
import subprocess
import sys
import util
import gen
import providers.bash as bash
import providers.chef as chef
import logging as log
from argparse import RawTextHelpFormatter
from subprocess import CalledProcessError

def do_genconf(options):
    """
    Wraps calls to the gen library and instanciates configuration for a given provider.
    """

    # Make sure to exit if --config is not passed when using non-interactive
    if not options.is_interactive:
      if not options.config:
        log.error("Must pass --config when using non-interactive mode.")
        sys.exit(1)

    # Interpolate the commands in genconf.py to gen library | i.e., set the args in gen/__init__.py from our genconf.py commands 
    gen_options = gen.get_options_object()
    gen_options.log_level = options.log_level
    gen_options.config = options.config
    gen_options.output_dir = options.output_dir

    if options.is_interactive:
      gen_options.assume_defaults = False
      gen_options.non_interactive = False
    else:
      gen_options.assume_defaults = True
      gen_options.non_interactive = True

    # Generate installation-type specific configuration
    if options.installer_format == 'bash':
        gen_out = do_provider(gen_options, bash, ['bash', 'centos', 'onprem'])
    elif options.installer_format == 'chef':
        gen_out = do_provider(gen_options, chef, ['chef', 'centos', 'onprem'])
    else:
        log.error("No such installer format: %s", options.installer_format)
        sys.exit(1)
    
    # Pass the arguments from gen_out to download, specifically calling the bootstrap_id value
    fetch_bootstrap(gen_out.arguments['channel_name'], gen_out.arguments['bootstrap_id'])


def do_provider(options, provider_module, mixins):
    gen_out = gen.generate(
        options=options,
        mixins=mixins,
        extra_cluster_packages=['onprem-config']
        )
    provider_module.generate(gen_out, options.output_dir)
    return gen_out


def fetch_bootstrap(channel_name, bootstrap_id):
    bootstrap_filename = "{}.bootstrap.tar.xz".format(bootstrap_id)
    dl_url = "https://downloads.mesosphere.com/dcos/{}/bootstrap/{}".format(
          channel_name, 
          bootstrap_filename
        )
    save_path = "/genconf/serve/bootstrap/{}".format(bootstrap_filename)

    def cleanup_and_exit():
        if os.path.exists(save_path):
            try:
                os.remove(save_path)
            except OSError as ex:
                log.error(ex.strerror)
        sys.exit(1)

    if not os.path.exists(save_path):
        # Check if there is an in-container copy of the bootstrap tarball, and
        # if so copy it across
        local_cache_filename = "/artifacts/" + bootstrap_filename
        if os.path.exists(local_cache_filename):
            log.info("Copying bootstrap out of cache")
            try:
                subprocess.check_call(['cp', local_cache_filename, save_path])
            except (KeyboardInterrupt, CalledProcessError) as ex:
                log.error("Copy failed or interrupted %s", ex.cmd)
                cleanup_and_exit()

        log.info("Downloading bootstrap tarball from %s", dl_url)
        curl_out = ""
        try:
            subprocess.check_call(['mkdir', '-p', '/genconf/serve/bootstrap/'])
            curl_out = subprocess.check_output([
                "/usr/bin/curl", "-fsSL", "-o", save_path, dl_url])
        except (KeyboardInterrupt, CalledProcessError) as ex:
            log.error("Download failed or interrupted %s", curl_out)
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

    # Whether to output chef or bash
    parser.add_argument('--installer-format', default='bash', type=str, choices=['bash', 'chef'], help='Type of installation. Bash or chef currently supported.')

    # Log level
    parser.add_argument('-l', '--log-level', default='info', type=str, choices=['debug', 'info'], help='Log level. Info or debug')

    # Output directory
    parser.add_argument('-o', '--output-dir', default='/genconf/serve', type=str, help='Output directory for genconf')

    # Config file override
    parser.add_argument('-c', '--config', type=str, help='Path to config.json')

    # Setup subparsers
    subparsers = parser.add_subparsers(title='commands')

    # interactive subcommand
    interactive = subparsers.add_parser('interactive')
    interactive.set_defaults(is_interactive=True)

    # non-interactive subcommand
    non_interactive = subparsers.add_parser('non-interactive')
    non_interactive.set_defaults(is_interactive=False)

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
   
    # Use an if rather than try/except since lots of things inside could throw
    # an AttributeError.
    if hasattr(options, 'is_interactive'):
        do_genconf(options)
        sys.exit(0)
    else:
        parser.print_help()
        log.error("Must use a subcommand")
        sys.exit(1)


if __name__ == '__main__':
    main()
