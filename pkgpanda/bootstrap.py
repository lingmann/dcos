"""Build a pkgpanda bootstrap tarball

Creates a functional pkgpanda filesystem at the given root.

Optionally will tar that up for use with the systemd files for use bootstrapping
new hosts remotely.

TODO(cmaloney): Support only installing a subset of the packages.

Usage:
    pkgpanda-mkbootstrap (tarball|container) [--role=<role>...] <root> <package>...

"""

import os
import os.path
import shutil
import sys

import pkgpanda
from docopt import docopt
from pkgpanda.util import make_tar, rewrite_symlinks, write_json


def make_file(name):
    with open(name, 'a'):
        pass


def main():
    arguments = docopt(__doc__)
    os.umask(0o022)

    root = os.path.abspath(arguments['<root>'])

    def make_abs(path):
        return os.path.join(root, path)

    pkgpanda_root = make_abs("opt/mesosphere")
    repository = pkgpanda.Repository(os.path.join(pkgpanda_root, "packages"))

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
    config_dir = make_abs("etc/mesosphere/roles/")
    if os.path.exists(config_dir):
        shutil.rmtree(config_dir)
    os.makedirs(config_dir)
    for role in arguments['--role']:
        make_file(os.path.join(config_dir, role))

    # Activate the packages inside the repository.
    # Do generate dcos.target.wants inside the root so that we don't
    # try messing with /etc/systemd/system.
    install = pkgpanda.Install(pkgpanda_root, config_dir, True, False, True, True)
    install.activate(repository, repository.load_packages(pkg_ids))

    # Remove dcos.target.wants from the install since it won't be used
    # on final install systems. Machines should run a `pkgpanda setup`
    # to activate / start all the systemd services for that specific
    # machine.
    shutil.rmtree(make_abs("opt/mesosphere/dcos.target.wants"))

    # Mark the tarball as a bootstrap tarball/filesystem so that
    # dcos-setup.service will fire.
    make_file(make_abs("opt/mesosphere/bootstrap"))

    # Write out an active.json for the bootstrap tarball
    write_json("active.json", pkg_ids)

    # Rewrite all the symlinks to point to /opt/mesosphere
    rewrite_symlinks(root, root, "/")

    if arguments['tarball']:
        make_tar("bootstrap.tar.xz", pkgpanda_root)
        sys.exit(0)

    if arguments['container']:
        # Setup base systemd units.
        # Print (or run) systemd-nspawn command.
        raise NotImplementedError()

    # Shouldn't be reached (tarball and root are only modus operandi)
    assert False
