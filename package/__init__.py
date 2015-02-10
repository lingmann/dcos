#!/usr/bin/env python3

"""
Packages have ids for looking at the fs. Only one package of an id may
be installed. There aren't sub-versions or anything at that level.

Each package contains a usage.json.

Note that we don't do anything other than listing installed packages, and sorting
versions for components in UI. The actual ordering of versions is arbitrary because
version numbers are hard. Things just work better if you follow something like
semantic versioning.

The usage.json describes the kind of data inside the package.
 Either:
 1. mesos
 2. mesos-module
 3. config

A package must be only one kind, and can only be enabled/disabled as a
whole.

usage.json format

{
  "mesos-module": ...
  "mesos": {
    "version": "version-string"
  }
}

run_base folder layout
######################################

/config # Contains symlinks to current active configuration files.
  mesos-master
  mesos-slave
  ...
/mesos # Current installed mesos version


Config package layout
########################################

/config # File containing the flags in whatever format is right for the kind.


Mesos package layout
#########################################
mesos install to the given directory.


"""
import json
import os
import os.path
import shutil
import urllib.parse
import urllib.request
from tempfile import NamedTemporaryFile

from package.exceptions import RepositoryError
from package.kinds import Package


def validate_active_set(packages):
    # Validate that the config is reasonable.

    def OneOfKind(kind):
        pkgs_kind = list(filter(lambda pkg: pkg.kind == kind, packages))
        if len(pkgs_kind) != 1:
            raise RepositoryError(
                "There should be exactly one active {0} packages. Current: {1}"
                .format(kind, " ".join(pkgs_kind)))

    # 1. There is exactly one mesos package.
    OneOfKind("mesos")

    # 2. There is exactly one config package.
    OneOfKind("config")

    # Check that the config package is the right kind for this host.


def get_env_file(packages):
    """Get the command line options to activate the given package list."""
    raise NotImplementedError()


class Remote:

    def fetch_and_extract(id):
        raise NotImplementedError()


class RemoteUrl(Remote):

    """Remote repository with all pacakges in a folder as tarballs."""

    def __init__(self, url):
        # TODO(cmaloney): Validate url format?
        self.__url = url

    def fetch_and_extract(self, id, target):
        # TODO(cmaloney): Switch to mesos-fetcher or aci or something so
        # all the logic can go away, we gain integrity checking, etc.
        filename = id + ".tar.gz"
        url = urllib.parse.urljoin(self.__url, filename)
        with NamedTemporaryFile(suffix=".tar.gz") as tmp_file:
            with urllib.request.urlopen(url) as response:
                shutil.copyfileobj(response, tmp_file)

            # Extract the package
            shutil.ubpack_archive(tmp_file.name, target)


# TODO(cmaloney): Add support for RemoteGithub, useful for grabbing config tarbals.
def GetFirstPackageOfKind(packages, kind):
    for package in packages:
        if package.kind == kind:
            return package

    raise ValueError("No package of kind {0} in packages {1}".format(kind, packages))


class Repository:

    def __init__(self, path):
        self.__path = path

    def package_path(self, id):
        return os.path.join(self.__path, id)

    def list(self):
        """List the available packages in the repository.

        A package is a folder which contains a usage.json"""
        packages = set()
        for id in os.listdir(self.__path):
            if os.path.exists(os.path.join(self.package_path(id), "usage.json")):
                packages.add(id)
        return packages

    def get_active(self):
        active_filename = self.get_active_filename()

        if not os.path.exists(active_filename):
            if os.path.exists(active_filename + ".old") or os.path.exists(active_filename + ".new"):
                raise RepositoryError(
                    "Broken deploy in history, see {0}.{new,old} for deploy state".format(active_filename))

        with open(active_filename) as f:
            return set(json.load(f))

    def load_packages(self, package_ids):
        loaded_packages = list()
        for id in package_ids:
            loaded_packages.append(Package.load(self.package_path(id)))
        return loaded_packages

    def integrity_check(self):
        # Check that all packages in the local repository have valid
        # signatures, are up to date, all packages valid contents, etc.
        raise NotImplementedError()

    def add(self, remote, id):
        # TODO(cmaloney): Supply a temporary directory to extract to
        # Then swap that into place.
        remote.fetch_and_extract(remote, id, self.package_path(id))

    def remove(self, id):
        shutil.rmtree(self.package_path(id))

    def get_active_filename(self):
        return os.path.join(self.__path, "active.json")

    # Updates the active file in a repository using a predictable atomic(ish) swap.
    class UpdateActive:

        def __init__(self, repository, packages):
            self.__active_name = repository.get_active_filename()
            self.__packages = packages

        def __enter__(self):
            # Write out new state
            with open(self.__active_name + '.new', 'w') as f:
                json.dump(list(self.__packages), f)
            # Archive old state
            os.replace(self.__active_name, self.__active_name + '.old')

        def __exit__(self, exc_type, exc_val, exc_tb):
            # Move new state into place if succesfully completed
            if exc_type is None:
                os.replace(self.__active_name + ".new", self.__active_name)


def activate(root, repository, packages):
    # Ensure the new set is reasonable
    validate_active_set(packages)

    # Get the new config package
    config_pkg = GetFirstPackageOfKind(packages, "config")
    config_path = config_pkg.path

    # Get the new mesos path
    mesos_pkg = GetFirstPackageOfKind(packages, "mesos")
    mesos_path = mesos_pkg.path

    config_dir = os.path.join(root, "config")
    mesos_dir = os.path.join(root, "mesos")

    # Swap into place as atomically as possible
    with Repository.UpdateActive(repository, packages):
        os.remove(config_dir)
        os.remove(mesos_dir)

        # Update filesystem symlinks for mesos, config
        os.symlink(config_path, config_dir)
        os.symlink(mesos_path, mesos_dir)
