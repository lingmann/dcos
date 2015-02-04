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
from kinds.py import Package


"""Validates that a set of packages can be used together, namely checking

1) There is exactly one mesos package
2) There is exactly one config package
"""


def activate(package_ids):
    # Load all the packages info, ensuring they are on the host filesystem
    loaded_packages = []
    for id in package_ids:
        loaded_packages.append(Package.load(id))

    # TODO(cmaloney) Integrity check (signature, checksum)?

    # Validate
    raise NotImplementedError()


def validate(packages):
    raise NotImplementedError()


# TODO(cmaloney): Support for framework packages(ala hdfs, marathon?)

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
