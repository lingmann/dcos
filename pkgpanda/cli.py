"""Panda package management

Usage:
  pkgpanda activate <id>... [options]
  pkgpanda activate --recover
  pkgpanda active [options]
  pkgpanda fetch --repository-url=<url> <id>... [options]
  pkgpanda list [options]
  pkgpanda remove <id>... [options]
  pkgpanda setup [options]

Options:
    --config-dir=<conf-dir>     Use an alternate directory for finding machine
                                configuration (roles, setup flags). [default: /etc/mesosphere/]
    --no-systemd                Don't try starting/stopping systemd services
    --no-block-systemd          Don't block waiting for systemd services to come up.
    --root=<root>               Testing only: Use an alternate root [default: /opt/mesosphere]
    --repository=<repository>   Testing only: Use an alternate local package
                                repository directory [default: /opt/mesosphere/packages]
    --rooted-systemd            Use $ROOT/dcos.target.wants for systemd management
                                rather than /etc/systemd/system/dcos.target.wants
"""

import json
import os.path
import sys
from itertools import groupby
from os import umask
from subprocess import check_call
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import urlopen

from docopt import docopt
from pkgpanda import Install, PackageId, Repository, urllib_fetcher
from pkgpanda.constants import version
from pkgpanda.exceptions import PackageError, ValidationError
from pkgpanda.util import if_exists, load_json, load_string


def print_repo_list(packages):
    pkg_ids = list(map(PackageId, sorted(packages)))
    for name, group_iter in groupby(pkg_ids, lambda x: x.name):
        group = list(group_iter)
        if len(group) == 1:
            print(group[0])
        else:
            print(name + ':')
            for package in group:
                print("  " + package.version)


def setup(install, repository):
    # These files should be set by the environment which initially builds
    # the host (cloud-init).
    repository_url = if_exists(load_string, install.get_config_filename("setup-flags/repository-url"))

    # If there is 1+ master, grab the active config from a master. If the
    # config can't be grabbed from any of them, fail.
    def fetcher(id, target):
        return urllib_fetcher(repository_url, id, target)

    # Copy host/cluster-specific packages from setup-packages folder into
    # the repository. Do not overwrite or merge existing packages, hard fail
    # instead.
    setup_pkg_dir = install.get_config_filename("setup-packages")
    for pkg_id_str in os.listdir(setup_pkg_dir):
        if not PackageId.is_id(pkg_id_str):
            print("Invalid package id in setup package: {}".format(pkg_id_str))
            sys.exit(1)
        pkg_id = PackageId(pkg_id_str)
        if pkg_id.version != "setup":
            print("Setup packages (those in `{0}`) must have the version setup. Bad package: {1}"
                  .format(setup_pkg_dir, pkg_id_str))
            sys.exit(1)

        # Make sure there is no existing package
        if repository.has_package(pkg_id_str):
            print("WARNING: Ignoring already installed package {}".format(pkg_id_str))

        def copy_fetcher(id, target):
            src_pkg_path = os.path.join(setup_pkg_dir, pkg_id_str) + "/"
            check_call(["cp", "-rp", src_pkg_path, target])

        repository.add(copy_fetcher, pkg_id_str)

    to_activate = None
    if repository_url:
        # TODO(cmaloney): Support sending some basic info to the machine generating
        # the active list of packages.
        active_url = urljoin(repository_url, "config/active.json")
        try:
            req = urlopen(active_url)
            to_activate = json.loads(req.read().decode('utf-8'))
        except HTTPError as ex:
            print("Unable to get list of packages to activate from: {0}".format(active_url))
            print(ex)
            sys.exit(1)
        except ValueError as ex:
            print("Unable to decode as JSON: {0}".format(active_url))
            sys.exit(1)

        # Ensure all packages are local
        for package in to_activate:
            repository.add(fetcher, package)
    else:
        # Grab to_activate from the local filez
        to_activate = load_json(install.get_config_filename("setup-flags/active.json"))

    # Should be set by loading out of fs or from the local config server.
    assert to_activate is not None

    install.activate(repository, repository.load_packages(to_activate))


def main():
    arguments = docopt(__doc__, version="Panda Package Management {}".format(version))
    umask(0o022)

    # NOTE: Changing root or repository will likely break actually running packages.
    install = Install(
        os.path.abspath(arguments['--root']),
        os.path.abspath(arguments['--config-dir']),
        arguments['--rooted-systemd'],
        not arguments['--no-systemd'], not arguments['--no-block-systemd'])
    repository = Repository(os.path.abspath(arguments['--repository']))

    if arguments['setup']:
        try:
            setup(install, repository)
        except ValidationError as ex:
            print("Validation Error: {0}".format(ex))
            sys.exit(1)
        sys.exit(0)

    if arguments['list']:
        print_repo_list(repository.list())
        sys.exit(0)

    if arguments['active']:
        for pkg in sorted(install.get_active()):
            print(pkg)
        sys.exit(0)

    if arguments['fetch']:
        def fetcher(id, target):
            return urllib_fetcher(arguments['--repository-url'], id, target)

        for pkg_id in arguments['<id>']:
            # TODO(cmaloney): Make this not use escape sequences when not at a
            # `real` terminal.
            sys.stdout.write("\rFetching: {0}".format(pkg_id))
            sys.stdout.flush()
            try:
                repository.add(fetcher, pkg_id)
            except URLError as ex:
                print("\nUnable to fetch package {0}: {1}".format(pkg_id, ex.reason))
                sys.exit(1)
            sys.stdout.write("\rFetched: {0}\n".format(pkg_id))
            sys.stdout.flush()

        sys.exit(0)

    if arguments['activate']:
        if arguments['--recover']:
            took_action, msg = install.recover_swap_active()
            if not took_action:
                print("No recovery performed: {}".format(msg))
            sys.exit(0)
        else:
            try:
                install.activate(repository, repository.load_packages(arguments['<id>']))
            except ValidationError as ex:
                print("Validation Error: {0}".format(ex))
                sys.exit(1)
            except PackageError as ex:
                print("Package Error: {0}".format(ex))
            sys.exit(0)

    if arguments['remove']:
        # Make sure none of the packages are active
        active_packages = install.get_active()
        active = active_packages.intersection(set(arguments['<id>']))
        if len(active) > 0:
            print("Refusing to remove active packages {0}".format(" ".join(sorted(list(active)))))
            sys.exit(1)

        for pkg_id in arguments['<id>']:
            sys.stdout.write("\rRemoving: {0}".format(pkg_id))
            sys.stdout.flush()
            try:
                # Validate package id, that package is installed.
                PackageId(pkg_id)
                repository.remove(pkg_id)
            except ValidationError:
                print("\nInvalid package id {0}".format(pkg_id))
                sys.exit(1)
            except OSError as ex:
                print("\nError removing package {0}".format(pkg_id))
                print(ex)
                sys.exit(1)
            sys.stdout.write("\rRemoved: {0}\n".format(pkg_id))
            sys.stdout.flush()
        sys.exit(0)

    print("unknown command")
    sys.exit(1)


if __name__ == "__main__":
    main()
