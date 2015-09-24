#!/usr/bin/env python3
"""Generates DCOS packages and configuration."""

import argparse
import glob
import json
import os
import subprocess
import sys
from argparse import RawTextHelpFormatter
from subprocess import CalledProcessError


def do_genconf(options):
    args = []
    if options.installer_format == 'bash':
        args += ["/dcos-image/bash.py"]
    elif options.installer_format == 'chef':
        args += ["/dcos-image/chef.py"]
    else:
        print("ERROR: No such installer format:", options.installer_format)
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
    except CalledProcessError:
        print("ERROR: Config generator exited with an error code")
        sys.exit(1)


def check_prereqs():
    if not os.path.isfile('/genconf/ip-detect.sh'):
        print("ERROR: Missing /genconf/ip-detect.sh")
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

    if not os.path.exists(save_path):
        print("INFO: Downloading bootstrap tarball: {}".format(dl_url))
        curl_out = ""
        try:
            subprocess.check_call(['mkdir', '-p', '/genconf/serve/bootstrap/'])
            curl_out = subprocess.check_output([
                "/usr/bin/curl", "-fsSL", "-o", save_path, dl_url])
        except (KeyboardInterrupt, CalledProcessError) as ex:
            print("ERROR: Download failed or interrupted {}".format(ex))
            print(curl_out)
            if os.path.exists(save_path):
                try:
                    os.remove(save_path)
                except OSError as ex:
                    print("ERROR: {} - {}".format(ex.filename, ex.strerror))
            sys.exit(1)


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
        print("INFO: Merging user configuration: {}".format(user_json_path))
        config.update(load_json(user_json_path))
    else:
        print("INFO: No optional user configuration detected in {}".format(
            user_json_path))

    return config


def load_json(filename):
    try:
        with open(filename) as fname:
            return json.load(fname)
    except ValueError as ex:
        print("ERROR: Invalid JSON in {0}: {1}".format(filename, ex))
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
  2. Add ip-detect.sh script to $BUILD_DIR
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
        print("ERROR: Must use a subcommand")
        sys.exit(1)


if __name__ == '__main__':
    main()
