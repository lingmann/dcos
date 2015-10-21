#!/usr/bin/env python3
"""Generates DCOS packages and configuration."""

import argparse
import glob
import json
import os
import subprocess
import sys
import logging as log
from argparse import RawTextHelpFormatter
from subprocess import CalledProcessError

def do_genconf(options):
    args = []
    if options.installer_format == 'bash':
        args += ["/dcos-image/bash.py"]
    elif options.installer_format == 'chef':
        args += ["/dcos-image/chef.py"]
    else:
        log.error("No such installer format: %s", options.installer_format)
        sys.exit(1)

    args += [
        "--output-dir", "/genconf/serve",
        "--config", "/genconf/config.json",
        "--save-final-config", "/genconf/config-final.json"]

    if not options.is_interactive:
        args += [
            "--assume-defaults",
            "--non-interactive",
            "--save-user-config", "/genconf/config-user-output.json"]

    do_gen_wrapper(args)


def do_gen_wrapper(args):
    conf = load_config('/dcos-image/config.json', '/genconf/config-user.json')
    save_json(conf, '/genconf/config.json')
    check_prereqs()
    fetch_bootstrap(conf)
    symlink_bootstrap()
    try:
        subprocess.check_call(args, cwd='/dcos-image')
    except CalledProcessError as e:
        log.error("Config generator exited with an error code: %s %s", e.exitcode, e.output)
        sys.exit(1)


def check_prereqs():
    """
    Ensure we can ingest an ip-detect script written in an arbitrary language.
    Pkgpanda will ensure the script outputs a valid IPV4 or 6 address, but we 
    can't do that here since we're not on the host machine yet.
    """

    if not os.path.isfile('/genconf/ip-detect'):
        log.error("Missing /genconf/ip-detect")
        sys.exit(1)


def fetch_bootstrap(
        config,
        bootstrap_root="https://downloads.mesosphere.com/dcos"):
    """Download the DCOS bootstrap tarball to /genconf if it does not already
    exist."""

    bootstrap_filename = "{}.bootstrap.tar.xz".format(config['bootstrap_id'])
    dl_url = "{}/{}/bootstrap/{}".format(
        bootstrap_root, config['channel_name'], bootstrap_filename)
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

        log.info("Downloading bootstrap tarball:", dl_url)
        curl_out = ""
        try:
            subprocess.check_call(['mkdir', '-p', '/genconf/serve/bootstrap/'])
            curl_out = subprocess.check_output([
                "/usr/bin/curl", "-fsSL", "-o", save_path, dl_url])
        except (KeyboardInterrupt, CalledProcessError) as ex:
            log.error("Download failed or interrupted %s", curl_out)
            cleanup_and_exit()


def symlink_bootstrap(
        src_glob='/genconf/serve/bootstrap/*bootstrap.tar.xz',
        dest_dir='/dcos-image/packages'):
    """Create symlinks to files matched by src_glob in dest_dir. Useful for
    making the bootstrap tarballs discoverable by the gen scripts."""
    for src in glob.glob(src_glob):
        dest = os.path.join(dest_dir, os.path.basename(src))
        try:
            # print("INFO: Creating symlink {} => {}".format(src, dest))
            os.symlink(src, dest)
        except FileExistsError:
            continue


def load_config(base_json_path, user_json_path):
    """Merges JSON data from base_json_path with user_json_path (if present).
    and returns the result as a Dict. Anything in user_json_path will override
    the data in base_json_path."""

    config = load_json(base_json_path)
    if os.path.isfile(user_json_path):
        log.info("Merging user configuration:", user_json_path)
        config.update(load_json(user_json_path))
    else:
        log.info("No optional user configuration detected in ", user_json_path)

    return config


def load_json(filename):
    try:
        with open(filename) as fname:
            return json.load(fname)
    except ValueError as ex:
        log.error("Invalid JSON %s: %s", filename, ex)
        sys.exit(1)


def save_json(dict_in, filename):
    with open(filename, 'w') as fname:
        json.dump(dict_in, fname)


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
    parser.add_argument('--installer-format', default='bash', type=str, choices=['bash', 'chef'])

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
