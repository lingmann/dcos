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

from package.exceptions import RepositoryError
from package.kinds import Package


def valid_active_set(packages):
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


class Repository:

    def __init__(self, path):
        self.__path = path

    def list(self):
        """List the available packages in the repository.

        A package is a folder which contains a usage.json"""
        packages = set()
        for path in os.listdir(self.__path):
            print(path)
            if os.path.exists(os.path.join(self.__path, path, "usage.json")):
                packages.add(path)
        return packages

    def get_active(self):
        with open(os.path.join(self.__path, "active.json")) as f:
            return set(json.load(f))

    def load_packages(self, package_ids):
        loaded_packages = list()
        for id in package_ids:
            loaded_packages.append(Package.load(os.path.join(self.__path, id)))
        return loaded_packages

    def integrity_check(self):
        # Check that all packages in the local repository have valid
        # signatures, are up to date, etc.
        raise NotImplementedError()


def kinds():
    return Package.kinds.keys()

# Get the given package and unpack it on the local filesystem using the
# given id


def fetch(url, id):
    # Eventually we'll use the mesos fetcher...
    pass


def remove(id):
    pass

# Checks that

# Given a list of packge, derive what the mesos command line flags are to use
# all those packages


def get_flags(packages):
    pass


def get_state(packages):
    pass
# Save the list


def save_state(packages):
    pass


def get_kind(usage):
    for kind in kinds():
        if kind in usage:
            return kind
