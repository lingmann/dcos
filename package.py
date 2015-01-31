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

#TODO: /opt/mesosphere/packages
package_base = "tests/resources/packages"
usage_filename = "usage.json"
run_base = "/opt/mesosphere/dcos"

# TODO(cmaloney): Is Master / Is Slave?

def not_implemented():
  raise NotImplemented()

class Package:
  kinds = dict()

  def __init__(self, kind, path, usage):
    self.__kind = kind
    self.__path = path
    self.__usage = usage

  @attribute
  def kind(self):
    return self.__kind

  @attribute
  def path(self):
    return self.__path

  @attribute
  def usage(Self):
    return self.__usage

  @staticmethod
  def add_kind(name, class):
    if name in kinds:
      raise ValueError("Already have kind with name {0}".format(name))
    kinds[name] = class

  @staticmethod
  def load(id):
    path = os.path.join(package_base, id)
    usage_filename = os.path.join(path, usage_filename)
    with open(usage_filename) as f:
      usage = json.load(f)

    for kind in kinds:
      if kind in usage:
        return kinds[kind](path, usage)

    raise ValueError("Unknown package type.")



class Module(Package):
  Packages.add_kind()
  def __init__(self, path, usage):
    super().__init__('module', path, usage)
    self.__flags = usage['module']

    # Expand the module paths
    for lib in self.__flags:
      if lib['name']:
        raise ValueError("Packaged modules may not use name")
      else:
        lib['file'] = os.path.join(path, lib['file']);

        for module in lib['modules']:
          if 'name' not in module:
            raise ValueError("Modules must have names")

          # TODO(cmaloney): Add a mechanism for giving the list of
          # optional and mandatory parameters to provide a better
          # end-user configuration experience.
          if 'parameters' in module:
            raise ValueError("Packaged modules must not have default parameters.")

    #TODO(cmaloney): DEBUG
    print(self.__flags)

    @attribute
    def flags(self):
      return self.__flags

    usage['module']

    self.__path = path
    self.__usage = usage

class Mesos(Package):
  def __init__(self, path, usage):
    super().__init__('mesos', path, usage)
    info = usage['mesos']
    self.__version = info['version']

  @attribute
  def version(self):
    return self.__version

  def activate(self):
    os.symlink(self.path, os.path.join(run_base, "mesos"))

class Config(Package):
  def __init__(self, path, usage):
    super().__init__('config', path, usage):
    info = usage['config']
    self.__kind = info['kind']
    self.__version = info['version']

  @attribute
  def kind(self):
    # kind gives us a sanity check so we don't apply a master config to
    # a slave or vice versa.(I)
    return self.__kind

  @attribute
  def version(self):
    return self.__version

  def activate(self):

    # TODO(cmaloney): Check valid for this type of system (master, config)
    os.symlink(self.path + "/config", os.path.join(run_base, "config", self.kind))


class Systemd(Package):
  """Containts all the systemd files for running mesos"""
  def __init__(self, path, usage):
    raise NotImplementedError()

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
  has_mesos = False
  has_config = False
  has_systemd = False
  raise NotImplemented()


# TODO(cmaloney): Support for framework packages(ala hdfs, marathon?)

def kinds():
  return kind_dispatch.keys()

# Get the given package and unpack it on the local filesystem using the given id
def fetch(url, id):
  # Eventually we'll use the mesos fetcher...
  pass

def remove(id):
  pass

# Checks that
def validate(usage):
  pass

# Given a list of packge, derive what the mesos command line flags are to use
# all those packages
def get_flags(packages):
  pass

# Symlink in the package bits as needed so things like the active config
def activate(packages):
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

print(get_usage("mesos-0.22.0"))

print(get_kind(get_usage("mesos-0.22.0")))
