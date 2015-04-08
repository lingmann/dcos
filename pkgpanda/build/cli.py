
"""Panda package builder

Reads a buildinfo file, uses it to assemble the sources and determine the
package version, then builds the package in an isolated environment along with
the necessary dependencies.

Usage:
  mkpanda [options]
  mkpanda add <package-tarball> [options]
  mkpanda clean
  mkpanda list [options]
  mkpanda remove <name-or-id>... [options]
  mkpanda tree [--mkbootstrap [--role=<role>...]]

Options:
  --repository-path=<path>  Path to pkgpanda repository containing all the
                            dependencies. [default: ~/.pkgpanda/repository]
"""

import copy
import os.path
import sys
import tempfile
from os import mkdir, umask
from os.path import abspath, exists, expanduser, normpath
from shutil import copyfile, rmtree
from subprocess import CalledProcessError, check_call

import pkgpanda.build.constants
from docopt import docopt
from pkgpanda import Install, PackageId, Repository, extract_tarball
from pkgpanda.build import checkout_sources, fetch_sources, hash_checkout, sha1
from pkgpanda.cli import print_repo_list
from pkgpanda.exceptions import PackageError, ValidationError
from pkgpanda.util import load_json, load_string, make_tar, rewrite_symlinks, write_json, write_string


class DockerCmd:

    volumes = dict()
    environment = dict()
    container = str()

    def run(self, cmd):
        docker = ["docker", "run"]
        for host_path, container_path in self.volumes.items():
            docker += ["-v", "{0}:{1}".format(host_path, container_path)]

        for k, v in self.environment.items():
            docker += ["-e", "{0}={1}".format(k, v)]

        docker.append(self.container)
        docker += cmd
        check_call(docker)


# package {id, name} + repo -> package id
def get_package_id(repository, pkg_str):
    if PackageId.is_id(pkg_str):
        return pkg_str
    else:
        ids = repository.get_ids(pkg_str)
        if len(ids) == 0:
            print("No package with name {0} in repository {1}".format(pkg_str, repository.path))
            sys.exit(1)
        elif len(ids) > 1:
            print(
                "Multiple packages for name {} in repository ".format(pkg_str) +
                "Only one package of a name may be present when " +
                "using a name rather than id.")
            sys.exit(1)
        return str(ids[0])


def clean():
    # Run a docker container to remove src/ and result/
    cmd = DockerCmd()
    cmd.volumes = {
        abspath(""): "/pkg/:rw",
    }
    cmd.container = "ubuntu:14.04"
    cmd.run(["rm", "-rf", "/pkg/src", "/pkg/result"])


def add(repository, path):
    # Extract Package Id (Filename must be path/{pkg-id}.tar.xz).
    name = os.path.basename(path)

    if not name.endswith('.tar.xz'):
        print("ERROR: Can only add package tarballs which have names " +
              "like {pkg-id}.tar.xz")

    pkg_id = name[:-len('.tar.xz')]

    # Validate the package id
    PackageId(pkg_id)

    def fetch(_, target):
        extract_tarball(path, target)

    repository.add(fetch, pkg_id)


def main():
    arguments = docopt(__doc__, version="mkpanda {}".format(pkgpanda.build.constants.version))
    umask(0o022)

    # Load the repository
    repository = Repository(normpath(expanduser(arguments['--repository-path'])))

    # Repository management commands.
    if arguments['add']:
        add(repository, arguments['<package-tarball>'])
        sys.exit(0)

    if arguments['list']:
        print_repo_list(repository.list())
        sys.exit(0)

    if arguments['remove']:
        for package in arguments['<name-or-id>']:
            pkg_id = get_package_id(repository, package)
            # TODO(cmaloney): the str() here is ugly.
            repository.remove(pkg_id)
        sys.exit(0)

    if arguments['tree']:
        build_tree(repository, arguments['--mkbootstrap'], arguments['--role'])
        sys.exit(0)

    buildinfo = load_buildinfo()

    # Only clean in valid build locations (Why this is after buildinfo.json)
    if arguments['clean']:
        clean()
        sys.exit(0)

    # No command -> build package.
    build(buildinfo, repository)
    sys.exit(0)


def load_buildinfo(path=os.getcwd()):
    # Load the package build info.
    try:
        return load_json(os.path.join(path, "buildinfo.json"))
    except FileNotFoundError:
        print("ERROR: Unable to find `buildinfo.json` in `{}.".format(path))
        sys.exit(1)
    except ValueError as ex:
        print("ERROR:", ex)
        sys.exit(1)


def build_tree(repository, mkbootstrap, mkbootstrap_roles):
    if len(repository.list()) > 0:
        print("ERROR: Repository must be empty before 'mkpanda tree' can be used")
        sys.exit(1)
    # Treat the current directory as the base of a repository of packages.
    # The packages are in folders, each containing a buildinfo.json, build.
    # Load all the buildinfos, topo-sort the dependencies, then build if/when
    # needed (Check build_ids.json vs. new pull).
    packages = dict()
    for name in os.listdir():
        if os.path.isdir(name):
            if not os.path.exists(os.path.join(name, "buildinfo.json")):
                continue
            packages[name] = load_buildinfo(name)
            if packages[name]["name"] != name:
                print("ERROR: Package name inside buildinfo.json must match folder name.")
                print("ERROR: {} name is {}".format(name, packages[name]["name"]))
                sys.exit(1)

    # Check the requires and figure out a feasible build order
    # depth-first traverse the dependency tree, yielding when we reach a
    # leaf or all the dependencies of package have been built. If we get
    # back to a node without all it's dependencies built, error (likely
    # circular).
    # TODO(cmaloney): Add support for circular dependencies. They are doable
    # long as there is a pre-built version of enough of the packages.

    build_order = list()
    visited = set()
    built = set()

    def visit(name):
        # Visit the node for the first (and only time). Finding a node again
        # means a cycle and should be detected at caller.
        assert name not in visited
        visited.add(name)

        # Ensure all dependencies are built
        for require in sorted(packages[name].get("requires", list())):
            if require in built:
                continue
            if require in visited:
                print("ERROR: Circular dependency. Circular link {0} -> {1}".format(name, require))
                sys.exit(1)

            # TODO(cmaloney): Add support for id requires
            if PackageId.is_id(require):
                raise NotImplementedError("Requires of specific ids")

            if require not in packages:
                print("ERROR: Package {0} Require {1} not buildable from tree.".format(name, require))
                sys.exit(1)

            visit(require)

        build_order.append(name)
        built.add(name)

    # Since there may be multiple isolated dependency trees, iterate through
    # all packages to find them all.
    for name in sorted(packages.keys()):
        if name in visited:
            continue
        visit(name)

    built_package_paths = set()
    try:
        for name in build_order:
            print("Building: {}".format(name))
            check_call(["mkpanda"], cwd=abspath(name))

            # Activate the package so the things that depend on it will build right.
            package_id = load_string(os.path.join(name, "cache/last_build"))
            pkg_path = "{0}/{1}.tar.xz".format(name, package_id)
            add(repository, pkg_path)
            built_package_paths.add(pkg_path)

    finally:
        # Always clear out the temporary repository.
        check_call(["rm", "-rf", repository.path])

    # Build the tarball if requested, along with a "active.json"
    if mkbootstrap:
        # TODO(cmaloney): This does a ton of excess repeated work... Make
        # mkbootstrap be a library call, use the repository built during package
        # building rather than making a new one.
        print("Making bootstrap tarball")
        tmpdir = tempfile.mkdtemp("pkgpanda_bootstrap")
        cmd = ["pkgpanda-mkbootstrap", "tarball", tmpdir]
        for role in mkbootstrap_roles:
            cmd += ["--role={}".format(role)]
        cmd += list(sorted(built_package_paths))
        check_call(cmd)
        rmtree(tmpdir)


def build(buildinfo, repository):
    # Clean out src, result so later steps can use them freely for building.
    clean()

    # Build pkginfo over time, translating fields from buildinfo.
    pkginfo = {}

    # Build up the docker command arguments over time, translating fields as needed.
    cmd = DockerCmd()

    # TODO(cmaloney): one buildinfo -> multiple packages builds.
    # TODO(cmaloney): allow a shorthand for single source packages.
    sources = None
    if "sources" in buildinfo:
        sources = buildinfo['sources']
    elif "single_source" in buildinfo:
        sources = {buildinfo['name']: buildinfo['single_source']}
    else:
        raise ValidationError("Must specify at least one source to build " +
                              "package from using 'sources' or 'single_source'.")

    print("Fetching sources")
    # Clone the repositories, apply patches as needed using the patch utilities
    checkout_ids = fetch_sources(sources)

    # Add the sha1sum of the buildinfo.json + build file to the build ids
    build_ids = {"sources": checkout_ids}
    build_ids['buildinfo'] = sha1("buildinfo.json")
    build_ids['build'] = sha1("build")

    # Only fresh builds are allowed which don't overlap existing artifacts.
    if exists("result"):
        print("result folder must not exist. It will be made when the package " +
              "is built. {}".format(abspath("result")))
        sys.exit(1)

    # Packages need directories inside the fake install root (otherwise docker
    # will try making the directories on a readonly filesystem), so build the
    # install root now, and make the package directories in it as we go.
    install_dir = tempfile.mkdtemp(prefix="pkgpanda-")

    active_packages = list()
    active_package_names = set()
    # Verify all requires are in the repository.
    if 'requires' in buildinfo:
        # Final package has the same requires as the build.
        pkginfo['requires'] = buildinfo['requires']

        # TODO(cmaloney): Pull generating the full set of requires a function.
        bad_requires = False
        to_check = copy.deepcopy(buildinfo['requires'])
        if type(to_check) != list:
            print("`requires` in buildinfo.json must be an array of dependencies.")
            sys.exit(1)
        while to_check:
            pkg_str = to_check.pop(0)
            try:
                pkg_id = get_package_id(repository, pkg_str)
                if PackageId(pkg_id).name in active_package_names:
                    continue

                package = repository.load(pkg_id)

                # Mount the package into the docker container.
                cmd.volumes[package.path] = "/opt/mesosphere/packages/{}:ro".format(package.id)

                os.makedirs(os.path.join(install_dir, "packages/{}".format(package.id)))

                # Mark the package as active so we don't check it again and
                # infinite loop on cycles.
                active_packages.append(package)
                active_package_names.add(package.name)

                # Add the dependencies of the package to the set which will be
                # activated.
                # TODO(cmaloney): All these 'transitive' dependencies shouldn't
                # be available to the package being built, only what depends on
                # them directly.
                to_check += package.requires
            except ValidationError as ex:
                print("ERROR validating package needed as dependency {0}: {1}".format(pkg_str, ex))
                bad_requires = True
            except PackageError as ex:
                print("ERROR loading package needed as dependency {0}: {1}".format(pkg_str, ex))
                bad_requires = True

        if bad_requires:
            sys.exit(1)

    # Add requires to the package id, calculate the final package id.
    build_ids['requires'] = [str(x) for x in active_packages]
    version_base = hash_checkout(build_ids)
    version = None
    if "version_extra" in buildinfo:
        version = "{0}-{1}".format(buildinfo["version_extra"], version_base)
    else:
        version = version_base
    pkg_id = PackageId.from_parts(buildinfo['name'], version)

    # If the package is already built, don't do anything.
    pkg_path = abspath("{}.tar.xz".format(pkg_id))
    if exists(pkg_path):
        print("Package up to date. Not re-building.")
        return pkg_path

    checkout_sources(sources)

    # Copy over environment settings
    if 'environment' in buildinfo:
        pkginfo['environment'] = buildinfo['environment']

    # Activate the packages so that we have a proper path, environment
    # variables.
    # TODO(cmaloney): RAII type thing for temproary directory so if we
    # don't get all the way through things will be cleaned up?
    install = Install(install_dir, None, True, False, True)
    install.activate(repository, active_packages)
    # Rewrite all the symlinks inside the active path because we will
    # be mounting the folder into a docker container, and the absolute
    # paths to the packages will change.
    # TODO(cmaloney): This isn't very clean, it would be much nicer to
    # just run pkgpanda inside the package.
    rewrite_symlinks(install_dir, repository.path, "/opt/mesosphere/packages/")

    docker_name = buildinfo.get('docker', 'ubuntu:14.04')
    if 'docker' in buildinfo:
        print("WARNING: Specifying docker explicitly shold be avoided.")
        print("This option will be removed once enough of the dependencies " +
              "are in pkgpanda form that everything can just use pkgpanda " +
              "dependencies.")
    cmd.container = docker_name

    print("Building package in docker")

    # TODO(cmaloney): Run as a specific non-root user, make it possible
    # for non-root to cleanup afterwards.
    # Run the build, prepping the environment as necessary.
    write_json("src/build_ids.json", checkout_ids)

    mkdir("result")

    # Copy the build info to the resulting tarball
    copyfile("src/build_ids.json", "result/build_ids.json")
    copyfile("buildinfo.json", "result/buildinfo.json")

    write_json("result/pkginfo.json", pkginfo)

    # Make the folder for the package we are building. If docker does it, it
    # gets auto-created with root permissions and we can't actually delete it.
    os.makedirs(os.path.join(install_dir, "packages", str(pkg_id)))

    # TOOD(cmaloney): Disallow writing to well known files and directories?
    # Source we checked out
    cmd.volumes.update({
        # TODO(cmaloney): src should be read only...
        abspath("src"): "/pkg/src:rw",
        # The build script
        abspath("build"): "/pkg/build:ro",
        # Getting the result out
        abspath("result"): "/opt/mesosphere/packages/{}:rw".format(pkg_id),
        install_dir: "/opt/mesosphere:ro"
        })
    cmd.environment = {
        "PKG_VERSION": version,
        "PKG_NAME": buildinfo['name'],
        "PKG_ID": pkg_id,
        "PKG_PATH": "/opt/mesosphere/packages/{}".format(pkg_id)
    }

    try:
        # TODO(cmaloney): Run a wrapper which sources
        # /opt/mesosphere/environment then runs a build. Also should fix
        # ownership of /opt/mesosphere/packages/{pkg_id} post build.
        cmd.run([
            "/bin/bash",
            "-o", "nounset",
            "-o", "pipefail",
            "-o", "errexit",
            "/pkg/build"])
    except CalledProcessError as ex:
        print("ERROR: docker exited non-zero: {}".format(ex.returncode))
        print("Command: {}".format(' '.join(ex.cmd)))
        sys.exit(1)

    # Clean up the temporary install dir used for dependencies.
    # TODO(cmaloney): Move to an RAII wrapper.
    rmtree(install_dir)

    print("Building package tarball")

    # TODO(cmaloney)  build info should be copied in here but can't really
    # because of docker and crazy folder root permissions...
    write_string("cache/last_build", str(pkg_id))

    # Bundle the artifacts into the pkgpanda package
    make_tar(pkg_path, "result")
    print("Package built, available at {}".format(pkg_path))
    return pkg_path


if __name__ == "__main__":
    main()
