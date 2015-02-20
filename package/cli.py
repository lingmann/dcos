
"""DCOS Package management local utility

Usage:
  pkgpanda bootstrap [options]
  pkgpanda list [options]
  pkgpanda active [options]
  pkgpanda fetch [options] <id>
  pkgpanda activate [options] <id>...

Options:
    --root=<root>               Use an alternate root (useful for debugging) [default: /opt/mesosphere]
    --repository=<repository>   Use an alternate local package repository directory[default: /opt/mesosphere/]
    --systemd=<systemd-dir>     Use an alternative directory for systemd. [default: /etc/systemd/dcos.target.wants/]
"""
import json
import os.path
import sys
from urllib.parse import urljoin
from urllib.request import urlopen

from docopt import docopt
from package import Install, Repository, urllib_fetcher
from package.constants import version
from package.util import load_json, load_string


def bootstrap(install, repository, arguments):
    # These files should be set by the environment which initially builds
    # the host (cloud-init).
    masters = None
    if os.path.exists("/etc/dcos/bootstrap-flags/masters"):
        masters = load_json("/etc/dcos/bootstrap-flags/masters")

    repository_url = None
    if os.path.exists("/etc/dcos/bootstrap-flags/repository-url"):
        repository_url = load_string("/etc/dcos/bootstrap-flags/repository-url")

    # If there is 1+ master, grab the active config from a master. If the
    # config can't be grabbed from any of them, fail.
    def fetcher(id, target):
        return urllib_fetcher(repository_url, id, target)

    to_activate = None
    if masters is not None:
        raise NotImplementedError()
        # Get active package list for machine from one of the masters
        # NOTE: Need to pass it base level of machine info so it can classify
        # This machine
        for master in masters:
            try:
                with urlopen(urljoin(repository_url, "/config/active.json")) as active_file:
                    to_activate = json.read(active_file)
                break
            except:
                pass

        if to_activate is None:
            print("Unable to get list of packages to activate from master.")
            sys.exit(1)

        # Ensure all packages are

        for package in to_activate:
            repository.add(fetcher, package)
    else:
        # Grab to_activate from the local filesystem
        to_activate = load_json("/opt/mesosphere/bootstrap/active.json")

    # Should be set by loading out of fs or from one of the masters.
    assert to_activate is not None

    install.activate(to_activate)


def main():
    arguments = docopt(__doc__, version="DCOS Package {}".format(version))

    # TODO(cmaloney): DEBUG
    print(arguments)

    # NOTE: Changing root or repository will likely break actually running packages.
    install = Install(os.path.abspath(arguments['--root']), os.path.abspath(arguments['--systemd']))
    repository = Repository(os.path.abspath(arguments['--repository']))

    if arguments['bootstrap']:
        bootstrap(install, repository, arguments)
        sys.exit(0)

    print("unknown command")
    sys.exit(1)
    return 0


if __name__ == "__main__":
    main()
