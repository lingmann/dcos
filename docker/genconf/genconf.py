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


def do_interactive(options):
    conf = load_config('/dcos-image/config.json', '/genconf/config-user.json')
    save_json(conf, '/genconf/config.json')
    check_prereqs()
    fetch_bootstrap(conf)
    symlink_bootstrap()
    subprocess.check_call([
        "/dcos-image/bash.py", "--output-dir", "/genconf/serve", "--config",
        "/genconf/config.json"
    ], cwd='/dcos-image')


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
        bootstrap_root, config['release_name'], bootstrap_filename)
    save_path = "/genconf/serve/bootstrap/{}".format(bootstrap_filename)
    save_dir = os.path.dirname(save_path)

    if not os.path.exists(save_path):
        print("INFO: Downloading bootstrap tarball: {}".format(dl_url))
        wget_out = ""
        try:
            wget_out = subprocess.check_output([
                "/usr/bin/wget", "-P", save_dir, "-nv", dl_url])
        except (KeyboardInterrupt, CalledProcessError) as ex:
            print("ERROR: Download failed or interrupted {}".format(ex))
            print(wget_out)
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
  3. Add config-user.json to $BUILD_DIR (optional)

Interactive Configuration
  1. Build DCOS artifacts:
     docker run -it -v "$BUILD_DIR":/genconf dcos-genconf interactive
'''
    parser = argparse.ArgumentParser(
        description=desc, formatter_class=RawTextHelpFormatter)
    subparsers = parser.add_subparsers(title='commands')

    # interactive subcommand
    interactive = subparsers.add_parser('interactive')
    interactive.set_defaults(func=do_interactive)

    # Parse the arguments and dispatch.
    options = parser.parse_args()

    # Use an if rather than try/except since lots of things inside could throw
    # an AttributeError.
    if hasattr(options, 'func'):
        options.func(options)
        sys.exit(0)
    else:
        parser.print_help()
        print("ERROR: Must use a subcommand")
        sys.exit(1)


if __name__ == '__main__':
    main()
