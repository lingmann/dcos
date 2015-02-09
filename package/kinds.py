import json
import os

from package.constants import run_base, usage_filename
from package.exceptions import PackageError


# TODO(cmaloney): Validate usage.keys() should always be length 1.
# TODO(cmaloney): Is Master / Is Slave?
class Package:
    kinds = dict()

    def __init__(self, kind, path, usage):
        self.__kind = kind
        self.__path = path
        self.__usage = usage

    @property
    def kind(self):
        return self.__kind

    @property
    def path(self):
        return self.__path

    @property
    def usage(self):
        return self.__usage

    @staticmethod
    def add_kind(name, cls):
        if name in Package.kinds:
            raise ValueError("Already have kind with name {0}".format(name))
        Package.kinds[name] = cls

    @staticmethod
    def load(path):
        filename = os.path.join(path, usage_filename)
        try:
            with open(filename) as f:
                usage = json.load(f)
        except FileNotFoundError as ex:
            raise PackageError("No / unreadable usage.json in package: {0}".format(ex.strerror))

        for kind in Package.kinds:
            if kind in usage:
                return Package.kinds[kind](path, usage)

        raise ValueError("Unknown package type: {0}.".format(usage.keys()))


class Module(Package):

    def __init__(self, path, usage):
        super().__init__('module', path, usage)
        self.__flags = usage['module']

        # Expand the module paths
        for lib in self.__flags:
            if lib['name']:
                raise ValueError("Packaged modules may not use name")
            else:
                lib['file'] = os.path.join(path, lib['file'])

            for module in lib['modules']:
                if 'name' not in module:
                    raise ValueError("Modules must have names")

                # TODO(cmaloney): Add a mechanism for giving the list of
                # optional and mandatory parameters to provide a better
                # end-user configuration experience.
                if 'parameters' in module:
                    raise ValueError(
                        "Packaged modules must not have default parameters.")

    @property
    def flags(self):
        return self.__flags


class Mesos(Package):

    def __init__(self, path, usage):
        super().__init__('mesos', path, usage)
        info = usage['mesos']
        self.__version = info['version']

    @property
    def version(self):
        return self.__version

    def activate(self):
        os.symlink(self.path, os.path.join(run_base, "mesos"))


class Config(Package):

    def __init__(self, path, usage):
        super().__init__('config', path, usage)
        info = usage['config']
        self.__node_types = info['node_type']
        self.__version = info['version']

    @property
    def node_type(self):
        # kind gives us a sanity check so we don't apply a master config to
        # a slave or vice versa.(I)
        return self.__node_type

    @property
    def version(self):
        return self.__version

    def activate(self):

        # TODO(cmaloney): Check valid for this type of system (master, config)
        os.symlink(
            self.path + "/config", os.path.join(run_base, "config", self.node_type))


Package.add_kind('config', Config)
Package.add_kind('mesos', Mesos)
Package.add_kind('module', Module)
