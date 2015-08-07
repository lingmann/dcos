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
from subprocess import CalledProcessError, check_call

from pkgpanda.exceptions import InstallError, PackageError, ValidationError
from pkgpanda.util import extract_tarball, if_exists, load_json, write_json, write_string

# TODO(cmaloney): Can we switch to something like a PKGBUILD from ArchLinux and
# then just do the mutli-version stuff ourself and save a lot of re-implementation?

reserved_env_vars = ["LD_LIBRARY_PATH", "PATH"]
env_header = """# Pandapkg provided environment variables
LD_LIBRARY_PATH={0}/lib
PATH={0}/bin:/usr/bin\n\n"""
env_export_header = """# Pandapkg provided environment variables
export LD_LIBRARY_PATH={0}/lib
export PATH="{0}/bin:$PATH"\n\n"""

name_regex = "^[a-zA-Z0-9@_+][a-zA-Z0-9@._+\-]*$"
version_regex = "^[a-zA-Z0-9@_+:.]+$"


# Manage starting/stopping all systemd services inside a folder.
class Systemd:

    def __init__(self, unit_directory, active, block):
        self.__active = active
        self.__block = block
        self.__unit_directory = unit_directory

    def stop_all(self):
        if not self.__active:
            return
        if not os.path.exists(self.__unit_directory):
            return
        for name in os.listdir(self.__unit_directory):
            # Skip directories
            if os.path.isdir(os.path.join(self.__unit_directory, name)):
                continue
            try:
                cmd = ["systemctl", "stop", name]
                if not self.__block:
                    cmd.append("--no-block")
                check_call(cmd)
            except CalledProcessError as ex:
                # If the service doesn't exist, don't error. This happens when a
                # bootstrap tarball has just been extracted but nothing started
                # yet during first activation.
                if ex.returncode != 5:
                    raise

    @property
    def unit_directory(self):
        return self.__unit_directory


class PackageId:

    @staticmethod
    def parse(id):
        parts = id.split('--')
        if len(parts) != 2:
            raise ValidationError(
                "Invalid package id {0}. Package ids may only ".format(id) +
                "contain one '--' which seperates the name and version")

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
    def is_id(package_str):
        return package_str.count('--') == 1

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
        return str(self.__id)


# Check that a set of packages is reasonable.
def validate_compatible(packages, roles):
    # Every package name appears only once.
    names = set()
    ids = set()
    for package in packages:
        if package.name in names:
            raise ValidationError(
                "Repeated name {0} in set of packages {1}".format(
                    package.name, ' '.join(map(lambda x: str(x.id), packages))))
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
def urllib_fetcher(base_url, id_str, target):
    assert base_url
    assert type(id_str) == str
    id = PackageId(id_str)
    # TODO(cmaloney): That file:// urls are allowed in base_url is likely a security hole.
    # TODO(cmaloney): Switch to mesos-fetcher or aci or something so
    # all the logic can go away, we gain integrity checking, etc.
    if base_url[-1] == '/':
        base_url = base_url[:-1]
    url = base_url + "/packages/{0}/{1}.tar.xz".format(id.name, id_str)
    # TODO(cmaloney): Use a private tmp directory so there is no chance of a user
    # intercepting the tarball + other validation data locally.
    fd, temp_filename = tempfile.mkstemp(suffix=".tar.xz")
    try:
        # Download the package.
        with os.fdopen(fd, "w+b") as f:
            with urllib.request.urlopen(url) as response:
                shutil.copyfileobj(response, f)

        # Extraction is an explicit seperate step from the download to minimize
        # chance of corruption when unpacking.
        extract_tarball(temp_filename, target)
    except:
        print("DEBUG: ", base_url, id_str, target, url)
        raise
    finally:
        try:
            os.remove(temp_filename)
        except:
            pass


class Repository:

    def __init__(self, path):
        self.__path = os.path.abspath(path)
        self.__packages = None

    @property
    def path(self):
        return self.__path

    def package_path(self, id):
        return os.path.join(self.__path, id)

    def get_ids(self, name):
        # TODO(cmaloney): There is a lot of excess re-parsing here...
        return list(pkg_id for pkg_id in self.list() if PackageId(pkg_id).name == name)

    def has_package(self, id):
        return id in self.list()

    def list(self):
        """List the available packages in the repository.

        A package is a folder which contains a pkginfo.json"""
        if self.__packages is not None:
            return self.__packages

        packages = set()
        if not os.path.exists(self.__path):
            return packages

        for id in os.listdir(self.__path):
            if PackageId.is_id(id):
                packages.add(id)
        self.__packages = packages
        return self.__packages

    # Load the given package
    def load(self, id):

        # Validate the package id.
        PackageId(id)

        path = self.package_path(id)
        filename = os.path.join(path, "pkginfo.json")
        pkginfo = None
        try:
            pkginfo = load_json(filename)
        except FileNotFoundError as ex:
            raise PackageError("No / unreadable pkginfo.json in {0}: {1}".format(id, ex.strerror)) from ex

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
    def add(self, fetcher, id, warn_added=True):
        # If the package already exists, return true
        package_path = self.package_path(id)
        if os.path.exists(package_path):
            if warn_added:
                print("Package already added.")
            return False

        # TODO(cmaloney): Supply a temporary directory to extract to
        # Then swap that into place, preventing partially-extracted things from
        # becoming an issue.
        fetcher(id, self.package_path(id))
        return True

    def remove(self, id):
        path = self.package_path(id)
        if not os.path.exists(path):
            return
        shutil.rmtree(path)


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

    def __init__(self, root, config_dir, rooted_systemd, manage_systemd, block_systemd, fake_path=False):
        assert type(rooted_systemd) == bool
        assert type(fake_path) == bool
        self.__root = os.path.abspath(root)
        self.__config_dir = os.path.abspath(config_dir) if config_dir else None
        if rooted_systemd:
            self.__systemd_dir = "{}/dcos.target.wants".format(root)
        else:
            self.__systemd_dir = "/etc/systemd/system/dcos.target.wants"
        self.__manage_systemd = manage_systemd
        self.__block_systemd = block_systemd

        # Look up the machine roles
        self.__roles = []
        if self.__config_dir:
            self.__roles = if_exists(os.listdir, os.path.join(self.__config_dir, "roles"))
            if self.__roles is None:
                self.__roles = []

        self.__well_known_dirs = ["bin", "etc", "include", "lib", self.__systemd_dir]

        self.__fake_path = fake_path

    def get_active(self):
        """the active folder has symlinks to all the active packages.

        Return the full package ids (The targets of the symlinks)."""
        active_dir = os.path.join(self.__root, "active")

        if not os.path.exists(active_dir):
            if os.path.exists(active_dir + ".old") or os.path.exists(active_dir + ".new"):
                raise InstallError(
                    ("Broken past deploy. See {0}.new for what the (potentially incomplete) new state should be " +
                     "and optionally {0}.old if it exists for the complete previous state.").format(active_dir))
            else:
                raise InstallError(
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
        return list(map(
            self._make_abs,
            self.__well_known_dirs + [
                "environment",
                "environment.export",
                "active",
                "active.buildinfo.full.json"
            ]))

    # Builds new working directories for the new active set, then swaps it into
    # place as atomically as possible.
    def activate(self, repository, packages):
        # Ensure the new set is reasonable.
        validate_compatible(packages, self.__roles)

        # Build the absolute paths for the running config, new config location,
        # and where to archive the config.
        active_names = self.get_active_names()
        active_dirs = list(map(self._make_abs, self.__well_known_dirs + ["active"]))

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
        env_contents = env_header.format("/opt/mesosphere" if self.__fake_path else self.__root)
        env_export_contents = env_export_header.format("/opt/mesosphere" if self.__fake_path else self.__root)

        active_buildinfo_full = {}

        # Add the folders, config in each package.
        for package in packages:
            # Package folders
            # NOTE: Since active is at the end of the folder list it will be
            # removed by the zip. This is the desired behavior, since it will be
            # populated later.
            # Do the basename since some well known dirs are full paths (dcos.target.wants)
            # while inside the packages they are always top level directories.
            for new, dir_name in zip(new_dirs, self.__well_known_dirs):
                dir_name = os.path.basename(dir_name)
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

            # Add to the environment.export contents
            env_export_contents += "# package: {0}\n".format(package.id)
            for k, v in package.environment.items():
                env_export_contents += "export {0}={1}\n".format(k, v)
            env_export_contents += "\n"

            # Add to the buildinfo
            try:
                active_buildinfo_full[package.name] = load_json(os.path.join(package.path, "buildinfo.full.json"))
            except FileNotFoundError:
                # TODO(cmaloney): These only come from setup-packages. Should update
                # setup-packages to add a buildinfo.full for those packages
                active_buildinfo_full[package.name] = None

        # Write out the new environment file.
        new_env = self._make_abs("environment.new")
        write_string(new_env, env_contents)

        # Write out the new environment.export file
        new_env_export = self._make_abs("environment.export.new")
        write_string(new_env_export, env_export_contents)

        # Write out the buildinfo of every active package
        new_buildinfo_meta = self._make_abs("active.buildinfo.full.json.new")
        write_json(new_buildinfo_meta, active_buildinfo_full)

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
        systemd = Systemd(self._make_abs(self.__systemd_dir), self.__manage_systemd, self.__block_systemd)

        # Ensure all the new active files exist
        for active in active_names:
            if not os.path.exists(active + extension):
                raise ValueError(
                    "Unable to swap active packages. Needed file {} doesn't exist.".format(active + extension))

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

        # TODO(pyronicide): DCOS-2535, systemd requires units to be both in the
        # root directory (/etc/systemd/system) *and* (for starting) in a
        # specific wants directory (dcos.target.wants). If they're not in both
        # places, units randomly move into a `not-loaded` state (which makes
        # for sad pandas). This treats dcos.target.wants as the single source
        # of truth and just sets things up locally.
        def manage_systemd_linking(method):
            base_systemd = os.path.normpath(
                os.path.join(self._make_abs(self.__systemd_dir), ".."))
            wants_path = self._make_abs(self.__systemd_dir)

            if not os.path.exists(wants_path):
                return

            for unit_name in os.listdir(wants_path):
                real_path = os.path.realpath(
                    os.path.join(wants_path, unit_name))
                if method == "cleanup":
                    try:
                        os.remove(os.path.join(base_systemd, unit_name))
                    except FileNotFoundError:
                        # This is going from an old to new version of DCOS.
                        pass
                elif method == "setup":
                    os.symlink(real_path, os.path.join(base_systemd, unit_name))
                else:
                    raise Exception("You called manage_systemd_linking wrong.")

        if archive:
            # TODO(cmaloney): stop all systemd services in dcos.target.wants
            record_state({"stage": "archive"})

            # Stop all systemd services
            systemd.stop_all()

            manage_systemd_linking("cleanup")

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

        manage_systemd_linking("setup")

        # All done with what we need to redo if host restarts.
        os.remove(state_filename)

    @property
    def manage_systemd(self):
        return self.__manage_systemd

    @property
    def systemd_dir(self):
        return self.__systemd_dir

    @property
    def root(self):
        return self.__root
