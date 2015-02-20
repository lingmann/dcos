#!/usr/bin/env python3

"""

See `docs/package_concepts.md` for the package layout.


Packages have ids. Ids are composed of a name + blob. The blob is never
introspected by the packaging stuff.

Each package contains a usage.json. That contains a list of requires as well as
envrionment variables from the package.

"""
import os
import os.path
import re
import shutil
import urllib.parse
import urllib.request
from itertools import chain
from tempfile import NamedTemporaryFile

from package.exceptions import PackageError, RepositoryError, ValidationError
from package.util import load_json

# TODO(cmaloney): Can we switch to something like a PKGBUILD from ArchLinux and
# then just do the mutli-version stuff ourself and save a lot of re-implementation?

# TODO(cmaloney): dcos.target.wants is what systemd ends up as.
well_known_dirs = ["bin", "etc", "lib", "dcos.target.wants"]
well_known_files = ["environment"]

name_regex = "^[a-zA-Z0-9@_+][a-zA-Z0-9@._+\-]*$"
version_regex = "^[a-zA-Z0-9@_+:]+$"


class PackageId:

    @staticmethod
    def parse(id):
        parts = id.rsplit('-', 1)
        if len(parts) != 2:
            raise ValidationError(
                "Invalid package id {0} must contain a '-' seperating the name and version".format(id))

        PackageId.validate_name(parts[0])
        PackageId.validate_version(parts[1])

        return parts[0], parts[1]

    @staticmethod
    def validate_name(name):
        # [a-zA-Z0-9@._+-]
        # May not start with '.' or '-'.
        if not re.match(name_regex, name):
            raise ValidationError("Invalid package name {0}. Must match the regex {1}".format(name, name_regex))

    @staticmethod
    def validate_version(version):
        # [a-zA-Z0-9@._+:]
        # May not contain a '-'.
        if not re.match(version_regex, version):
            raise ValidationError(
                "Invalid package version {0}. Must match the regex {1}".format(version, version_regex))

    def __init__(self, id):
        self.name, self.version = PackageId.parse(id)

    def __repr__(self):
        return '{0}-{1}'.format(self.name, self.version)


class Package:

    def __init__(self, path, id, usage):
        self.__id = id
        self.__path = path
        self.__usage = usage

    @property
    def environment(self):
        return self.__usage['environment']

    @property
    def id(self):
        return self.__id

    @property
    def name(self):
        return self.__id.name

    @property
    def path(self):
        return self.__path

    @property
    def requires(self):
        return self.__usage['requires']

    @property
    def version(self):
        return self.__id.version

    def __repr__(self):
        return id


# Check that a set of packages is reasonable.
def validate_compatible(packages):
    # Every package name appears only once.
    names = set()
    for package in packages:
        if package.name in names:
            raise ValidationError(
                "Repeated name {0} in set of packages {1}".format(package.name, ' '.join(packages)))
        names.add(package.name)

    # All requires are met.
    # NOTE: Requires are given just to make it harder to accidentally
    # break a cluster.

    # Environment variables in packages, mapping from variable to package.
    environment = dict()

    for package in packages:

        # All requirements of packages are met
        for requirement in package.requires:
            if requirement not in names:
                raise ValidationError("Package {0} requires {1} but that is not in the set of packages {2}",
                                      package,
                                      requirement,
                                      ' '.join(packages))

        # No repeated/conflicting environment variables.
        for var in package.environment:
            if var in environment:
                raise ValidationError(
                    "Repeated environment variable {0}. In both packages {1} and {2}.".format(
                        var, environment[var], package))
            environment[var] = package

    # TODO(cmaloney): More complete validation
    #  - There are no repeated file/folder in the well_known_dirs
    #  - There is a base set of required package names (pkgpanda, mesos, config)
    #  - The config is for this specific type of host (master, slave)?


# TODO(cmaloney): Add a github fetcher, useful for grabbing config tarballs.
def urllib_fetcher(self, base_url, id, target):
    assert base_url
    # TODO(cmaloney): Switch to mesos-fetcher or aci or something so
    # all the logic can go away, we gain integrity checking, etc.
    filename = id + ".tar.gz"
    url = urllib.parse.urljoin(base_url, filename)
    with NamedTemporaryFile(suffix=".tar.gz") as tmp_file:
        with urllib.request.urlopen(url) as response:
            shutil.copyfileobj(response, tmp_file)

        # Extract the package
        shutil.unpack_archive(tmp_file.name, target)


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

    # Load the given package
    def load(self, id):
        path = self.package_path(id)
        filename = os.path.join(path, "usage.json")
        usage = None
        try:
            usage = load_json(filename)
        except FileNotFoundError as ex:
            raise PackageError("No / unreadable usage.json in package: {0}".format(ex.strerror))

        if not isinstance(usage, dict):
            raise PackageError("Usage should be a dictionary, not a {0}".format(type(usage).__name__))

        return Package(path, id, usage)

    def load_packages(self, ids):
        packages = set()
        for id in ids:
            packages.add(self.load(id))

    def integrity_check(self):
        # Check that all packages in the local repository have valid
        # signatures, are up to date, all packages valid contents, etc.
        raise NotImplementedError()

    # Add the given package to the repository.
    # If the package is already in the repository does a no-op and returns false.
    # Returns true otherwise.
    def add(self, fetcher, id):
        # If the package already exists, return true
        package_path = self.package_path(id)
        if os.path.exists(package_path):
            return False

        # TODO(cmaloney): Supply a temporary directory to extract to
        # Then swap that into place, preventing partially-extracted things from
        # becoming an issue.
        fetcher(id, self.package_path(id))
        return True

    def remove(self, id):
        shutil.rmtree(self.package_path(id))


# A rooted instal lgtree.
# Inside the install tree there will be all the well known folders and files as
# described in `docs/package_concepts.md`
class Install:

    def __init__(self, root, systemd):
        self.__root = root
        self.__systemd = systemd

    def get_active(self):
        """the active folder has symlinks to all the active packages.

        Return the full package ids (The targets of the symlinks)."""
        active_dir = os.path.join(self.__root, "active")

        if not os.path.exists(active_dir):
            if os.path.exists(active_dir + ".old") or os.path.exists(active_dir + ".new"):
                raise RepositoryError(
                    ("Broken past deploy. See {0}.new for what the (potentially incomplete) new state shuold be " +
                     "and optionally {0}.old if it exists for the complete previous state.").format(active_dir))
            else:
                raise RepositoryError(
                    "Install directory {0} has no active folder. Has it been bootstrapped?".format(self.__root))

        ids = set()
        for name in os.listdir(active_dir):
            package_path = os.path.realpath(os.path.join(active_dir, name))
            # NOTE: We don't validate the id here because we want to be able to
            # cope if there is somethign invalid in the current active dir.
            ids.add(os.path.basename(package_path))

        return ids

    # Builds new working directories for the new active set, then swaps it into
    # place as atomically as possible.
    def activate(self, packages):
        # Ensure the new set is reasonable
        validate_compatible(packages)

        # Generate the new global directories, wiping out any previous
        # deploy attempt first.
        for name in chain(well_known_dirs, well_known_files):
            os.path.join(self.__root, name + ".new")

        for folder in ["bin", "etc", "lib"]:
            pass

        # The systemd new goes in /etc/systemd/dcos.target.wants.new rather than our install root

        # Swap into place.
