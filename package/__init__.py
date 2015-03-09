#!/usr/bin/env python3

"""

See `docs/package_concepts.md` for the package layout.


Packages have ids. Ids are composed of a name + blob. The blob is never
introspected by the packaging stuff.

Each package contains a pkginfo.json. That contains a list of requires as well as
envrionment variables from the package.

"""
import json
import os
import os.path
import re
import shutil
import tempfile
import urllib.parse
import urllib.request
from itertools import chain
from subprocess import check_call

from package.exceptions import PackageError, RepositoryError, ValidationError
from package.util import if_exists, load_json

# TODO(cmaloney): Can we switch to something like a PKGBUILD from ArchLinux and
# then just do the mutli-version stuff ourself and save a lot of re-implementation?

# TODO(cmaloney): dcos.target.wants is what systemd ends up as.
well_known_dirs = ["bin", "etc", "lib", "dcos.target.wants"]
reserved_env_vars = ["LD_LIBRARY_PATH", "PATH"]
env_header = """# Pandapkg provided environment variables
LD_LIBRARY_PATH={0}/lib
PATH=/usr/bin:{0}\n\n"""

name_regex = "^[a-zA-Z0-9@_+][a-zA-Z0-9@._+\-]*$"
version_regex = "^[a-zA-Z0-9@_+:.]+$"


# Manage starting/stopping all systemd services inside a folder.
class Systemd:

    def __init__(self, unit_dir, active=False):
        self.__active = active
        self.__dir = unit_dir

    def daemon_reload(self):
        if not self.__active:
            return
        check_call(["systemctl", "daemon-reload"])

    def start_all(self):
        if not self.__active:
            return
        for path in os.listdir(self.__dir):
            check_call(["systemctl", "start", path])

    def stop_all(self):
        if not self.__active:
            return
        if not os.path.exists(self.__dir):
            return
        for path in os.listdir(self.__dir):
            check_call(["systemctl", "stop", path])


class PackageId:

    @staticmethod
    def parse(id):
        parts = id.split('--')
        if len(parts) != 2:
            raise ValidationError(
                "Invalid package id {0}. Package ids may only contain one '--' " +
                "which seperates the name and version".format(id))

        PackageId.validate_name(parts[0])
        PackageId.validate_version(parts[1])

        return parts[0], parts[1]

    @staticmethod
    def from_parts(name, version):
        # TODO(cmaloney): This format, then parse is less than ideal.
        return PackageId("{0}--{1}".format(name, version))

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
        return '{0}--{1}'.format(self.name, self.version)


class Package:

    def __init__(self, path, id, pkginfo):
        if isinstance(id, str):
            id = PackageId(id)
        self.__id = id
        self.__path = path
        self.__pkginfo = pkginfo

    @property
    def environment(self):
        return self.__pkginfo.get('environment', dict())

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
        return frozenset(self.__pkginfo.get('requires', list()))

    @property
    def version(self):
        return self.__id.version

    def __repr__(self):
        return str(id)


# Check that a set of packages is reasonable.
def validate_compatible(packages, roles):
    # Every package name appears only once.
    names = set()
    ids = set()
    for package in packages:
        if package.name in names:
            raise ValidationError(
                "Repeated name {0} in set of packages {1}".format(
                    package.name, ' '.join(map(str, packages))))
        names.add(package.name)
        ids.add(str(package.id))

    # All requires are met.
    # NOTE: Requires are given just to make it harder to accidentally
    # break a cluster.

    # Environment variables in packages, mapping from variable to package.
    environment = dict()

    for package in packages:

        # Check that all requirements of the package are met.
        # Requirements can be specified on a package name or full version string.
        for requirement in package.requires:
            if requirement not in names and requirement not in ids:
                raise ValidationError("Package {0} requires {1} but that is not in the set of packages {2}".format(
                                          package.id,
                                          requirement,
                                          ', '.join(str(x.id) for x in packages)))

        # No repeated/conflicting environment variables with other packages as
        # well as magic system enviornment variables.
        for k, v in package.environment.items():
            if k in reserved_env_vars:
                raise ValidationError(
                    "{0} are reserved enviornment vars and cannot be specified in packages. Present in package {1}"
                    .format(", ".join(reserved_env_vars), package))
            if k in environment:
                raise ValidationError(
                    "Repeated environment variable {0}. In both packages {1} and {2}.".format(
                        k, v, package))
            environment[k] = package

    # TODO(cmaloney): More complete validation
    #  - There are no repeated file/folder in the well_known_dirs
    #       - Including the roles subfolders.
    #  - There is a base set of required package names (pkgpanda, mesos, config)
    #  - The config is for this specific type of host (master, slave)?


# TODO(cmaloney): Add a github fetcher, useful for grabbing config tarballs.
def urllib_fetcher(base_url, id, target):
    assert base_url
    # TODO(cmaloney): That file:// urls are allowed in base_url is likely a security hole.
    # TODO(cmaloney): Switch to mesos-fetcher or aci or something so
    # all the logic can go away, we gain integrity checking, etc.
    filename = id + ".tar.xz"
    url = urllib.parse.urljoin(base_url, filename)
    # TODO(cmaloney): Use a private tmp directory so there is no chance of a user
    # intercepting the tarball + other validation data locally.
    fd, temp_filename = tempfile.mkstemp(suffix=".tar.xz")
    try:
        # Download the package.
        with os.fdopen(fd, "w+b") as f:
            with urllib.request.urlopen(url) as response:
                shutil.copyfileobj(response, f)

        # Extract the package. If there are any errors, delete the folder being extracted to.
        # This is an explicit seperate step from the download to minimize chance of corruption when unpacking.
        # TODO(cmaloney): Validate as much as possible the extraction will pass before taking any action.
        try:
            assert os.path.exists(temp_filename)
            shutil.unpack_archive(temp_filename, target, "gztar")
        except:
            # If there are errors, we can't really cope since we are already in an error state.
            shutil.rmtree(target, ignore_errors=True)
            raise
    except:
        raise
    finally:
        try:
            os.remove(temp_filename)
        except:
            pass


class Repository:

    def __init__(self, path):
        self.__path = os.path.abspath(path)

    def package_path(self, id):
        return os.path.join(self.__path, id)

    def list(self):
        """List the available packages in the repository.

        A package is a folder which contains a pkginfo.json"""
        packages = set()
        for id in os.listdir(self.__path):
            if os.path.exists(os.path.join(self.package_path(id), "pkginfo.json")):
                packages.add(id)
        return packages

    # Load the given package
    def load(self, id):
        path = self.package_path(id)
        filename = os.path.join(path, "pkginfo.json")
        pkginfo = None
        try:
            pkginfo = load_json(filename)
        except FileNotFoundError as ex:
            raise PackageError("No / unreadable pkginfo.json in package: {0}".format(ex.strerror))

        if not isinstance(pkginfo, dict):
            raise PackageError("Usage should be a dictionary, not a {0}".format(type(pkginfo).__name__))

        return Package(path, id, pkginfo)

    def load_packages(self, ids):
        packages = set()
        for id in ids:
            packages.add(self.load(id))
        return packages

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


# Create folders and symlink files inside the folders. Allows multiple
# packages to have the same folder and provide it publicly.
def symlink_tree(src, dest):
    for name in os.listdir(src):
        src_path = os.path.join(src, name)
        dest_path = os.path.join(dest, name)
        # Symlink files and symlinks directly. For directories make a
        # real directory and symlink everything inside.
        # NOTE: We could relax this and follow symlinks, but then we
        # need to be careful about recursive filesystem layouts.
        if os.path.isdir(src_path) and not os.path.islink(src_path):
            if os.path.exists(dest_path):
                # We can only merge a directory into a directory.
                # We won't merge into a symlink directory because that could
                # result in a package editing inside another package.
                if not os.path.isdir(dest_path) and not os.path.islink(dest_path):
                    raise ValidationError(
                        "Can't merge a file `{0}` and directory (or symlink) `{1}` with the same name."
                        .format(src_path, dest_path))
            else:
                os.makedirs(dest_path)

            # Recuse into the directory symlinking everything so long as the directory isn't
            symlink_tree(src_path, dest_path)
        else:
            os.symlink(src_path, dest_path)


# A rooted instal lgtree.
# Inside the install tree there will be all the well known folders and files as
# described in `docs/package_concepts.md`
class Install:

    def __init__(self, root, config_dir, manage_systemd):
        self.__root = os.path.abspath(root)
        self.__config_dir = os.path.abspath(config_dir)
        self.__manage_systemd = manage_systemd

        # Look up the machine roles
        self.__roles = if_exists(os.listdir, os.path.join(self.__config_dir, "roles"))
        if self.__roles is None:
            self.__roles = []

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

    def has_flag(self, name):
        return os.path.exists(self.get_config_filename(name))

    def get_config_filename(self, name):
        return os.path.join(self.__config_dir, name)

    def _make_abs(self, name):
        return os.path.abspath(os.path.join(self.__root, name))

    def get_active_names(self):
        return list(map(self._make_abs, well_known_dirs + ["environment", "active"]))

    # Builds new working directories for the new active set, then swaps it into
    # place as atomically as possible.
    def activate(self, repository, packages):
        # Ensure the new set is reasonable.
        validate_compatible(packages, self.__roles)

        # Build the absolute paths for the running config, new config location,
        # and where to archive the config.
        active_names = self.get_active_names()
        active_dirs = list(map(self._make_abs, well_known_dirs + ["active"]))

        new_names = [name + ".new" for name in active_names]
        new_dirs = [name + ".new" for name in active_dirs]

        old_names = [name + ".old" for name in active_names]

        # Remove all pre-existing new and old directories
        for name in chain(new_names, old_names):
            if (os.path.exists(name)):
                if os.path.isdir(name):
                    shutil.rmtree(name)
                else:
                    os.remove(name)

        # Make the directories for the new config
        for name in new_dirs:
            os.makedirs(name)

        # Fill in all the new contents
        def symlink_all(src, dest):
            if not os.path.isdir(src):
                return

            symlink_tree(src, dest)

        # Set the new LD_LIBRARY_PATH, PATH.
        env_contents = env_header.format(self.__root)

        # Add the folders, config in each package.
        for package in packages:
            # Package folders
            # NOTE: Since active is at the end of the folder list it will be
            # removed by the zip. This is the desired behavior, since it will be
            # populated later.
            for new, dir_name in zip(new_dirs, well_known_dirs):
                pkg_dir = os.path.join(package.path, dir_name)
                assert os.path.isabs(new)
                assert os.path.isabs(pkg_dir)

                symlink_all(pkg_dir, new)

                # Symlink all applicable role-based config
                for role in self.__roles:
                    role_dir = os.path.join(package.path, "{0}_{1}".format(dir_name, role))
                    symlink_all(role_dir, new)

            # Add to the active folder
            os.symlink(package.path, os.path.join(self._make_abs("active.new"), package.name))

            # Add to the environment contents
            env_contents += "# package: {0}\n".format(package.id)
            for k, v in package.environment.items():
                env_contents += "{0}={1}\n".format(k, v)
            env_contents += "\n"

        # Write out the new environment file.
        new_env = self._make_abs("environment.new")
        with open(new_env, "w+") as f:
            f.write(env_contents)

        self.swap_active(".new")

    def recover_swap_active(self):
        state_filename = self._make_abs("install_progress")
        if not os.path.exists(state_filename):
            return False, "Path does not exist: {}".format(state_filename)
        state = load_json(state_filename)
        extension = state['extension']
        stage = state['stage']
        if stage == 'archive':
            self.swap_active(extension, True)
        elif stage == 'move_new':
            self.swap_active(extension, False)
        else:
            raise ValueError("Unexpected state to recover from {}".format(state))

        return True, ""

    # Does an atomic(ish) upgrade swap with support for recovering if
    # only part of the swap happens before a reboot.
    # TODO(cmaloney): Implement recovery properly.
    def swap_active(self, extension, archive=True):
        active_names = self.get_active_names()
        state_filename = self._make_abs("install_progress")
        systemd = Systemd(self._make_abs("dcos.target.wants"), self.__manage_systemd)

        # Record the state (atomically) on the filesystem so that if there is a
        # hard/fast fail at any point the activate swap can continue.
        def record_state(state):
            # Atomically write all the state to disk, swap into place.
            with open(state_filename + ".new", "w+") as f:
                state['extension'] = extension
                json.dump(state, f)
                f.flush()
                os.fsync(f.fileno())
            os.rename(state_filename + ".new", state_filename)

        if archive:
            # TODO(cmaloney): stop all systemd services in dcos.target.wants
            record_state({"stage": "archive"})

            # Stop all systemd services
            systemd.stop_all()

            # Archive the current config.
            for active in active_names:
                old_path = active + ".old"
                if os.path.exists(active):
                    os.rename(active, old_path)

        record_state({"stage": "move_new"})

        # Move new / with extension into active.
        # TODO(cmaloney): Capture any failures here and roll-back if possible.
        # TODO(cmaloney): Alert for any failures here.
        for active in active_names:
            new_path = active + extension
            os.rename(new_path, active)

        # Start all systemd services in dcos.target.wants
        systemd.daemon_reload()
        systemd.start_all()

        # All done.
        os.remove(state_filename)
