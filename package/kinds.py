import json
import os

from package.constants import usage_filename
from package.exceptions import PackageError


# TODO(cmaloney): Validate usage.keys() should always be length 1.
# TODO(cmaloney): Is Master / Is Slave?
class Package:
    kinds = dict()

    def __init__(self, kind, id, path, usage):
        self.__kind = kind
        self.__path = path
        self.__usage = usage
        self.__requires = usage['requires']

    @property
    def kind(self):
        return self.__kind

    @property
    def path(self):
        return self.__path

    @property
    def requires(self):
        return self.__requires

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


class Mesos(Package):

    def __init__(self, id, path, usage):
        super().__init__('mesos', id, path, usage)
        info = usage['mesos']
        self.__version = info['version']

    @property
    def version(self):
        return self.__version


class Config(Package):

    def __init__(self, id, path, usage):
        super().__init__('config', id, path, usage)
        info = usage['config']
        self.__node_types = info['node_type']
        self.__version = info['version']

    @property
    def node_type(self):
        # kind gives us a sanity check so we don't apply a master config to
        # a slave or vice versa.
        return self.__node_type

    @property
    def version(self):
        return self.__version


# Blobs used for zk, java, python, artemis/provisioning, packaging system, restart module
class Blob(Package):

    def __init__(self, id, path, usage):
        super().__init__('mesos', id, path, usage)
        info = usage['blob']
        self.__kind = info['kind']

Package.add_kind('config', Config)
Package.add_kind('mesos', Mesos)
Package.add_kind('blob', Blob)
