"""Build a pkgpanda bootstrap tarball

Creates a functional pkgpanda filesystem at the given root.

Optionally will tar that up for use with the systemd files for use bootstrapping
new hosts remotely.

TODO(cmaloney): Support only installing a subset of the packages.

Usage:
    pkgpandastrap (tarball|container) [--role=<role>...] <root> <package>...

"""

import os
import os.path
import shutil
from subprocess import check_call

import package
from docopt import docopt


def make_file(name):
    with open(name, 'a'):
        pass


def main():
    arguments = docopt(__doc__)

    root = os.path.abspath(arguments['<root>'])

    def make_abs(path):
        return os.path.join(root, path)

    pkgpanda_root = make_abs("opt/mesosphere")
    repository = package.Repository(os.path.join(pkgpanda_root, "packages"))

    # Fetch all the packages to the root
    pkg_ids = list()
    for pkg_path in arguments['<package>']:
        # Get the package id from the given package path
        filename = os.path.basename(pkg_path)
        if not filename.endswith(".tar.xz"):
            print("ERROR: Packages must be packaged / end with .tar.xz")
            sys.exit(1)
        pkg_id = filename[:-len(".tar.xz")]
        pkg_ids.append(pkg_id)

        # TODO(camloney): Allow grabbing packages via http.
        def local_fetcher(id, target):
            shutil.unpack_archive(pkg_path, target, "gztar")
        repository.add(local_fetcher, pkg_id)

    # Mark the appropriate roles.
    config_dir = make_abs("etc/mesosphere")
    if os.path.exists(config_dir):
        shutil.rmtree(config_dir)
    os.makedirs(config_dir)
    for role in arguments['--role']:
        make_file(os.path.join(config_dir, role))

    # Activate the packages inside the repository.
    install = package.Install(pkgpanda_root, config_dir, False)
    install.activate(repository, repository.load_packages(pkg_ids))

    if arguments['tarball']:
        check_call(["tar", "-cJf", "bootstrap.tar.xz", "-C", pkgpanda_root, "."])
        sys.exit(0)

    if arguments['container']:
        # Setup base systemd units.
        # Print (or run) systemd-nspawn command.
        raise NotImplementedError()

    # Shouldn't be reached (tarball and root are only modus operandi)
    assert False
