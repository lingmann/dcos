
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

Options:
  --repository-path=<path>  Path to pkgpanda repository containing all the
                            dependencies. [default: ~/.pkgpanda/repository]
"""

import copy
import os.path
import sys
import tempfile
from itertools import chain
from os import mkdir
from os.path import abspath, exists
from shutil import copyfile, rmtree
from subprocess import CalledProcessError, check_call

import pkgpanda.build.constants
from docopt import docopt
from pkgpanda import Install, PackageId, Repository, extract_tarball
from pkgpanda.build import checkout_source, hash_checkout, sha1
from pkgpanda.cli import print_repo_list
from pkgpanda.exceptions import PackageError, ValidationError
from pkgpanda.util import load_json, make_tar, write_json


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


def rewrite_symlinks(root, old_prefix, new_prefix):
    # Find the symlinks and rewrite them from old_prefix to new_prefix
    # All symlinks not beginning with old_prefix are ignored because
    # packages may contain arbitrary symlinks.
    for root_dir, dirs, files in os.walk(root):
        for name in chain(files, dirs):
            full_path = os.path.join(root_dir, name)
            if os.path.islink(full_path):
                # Rewrite old_prefix to new_prefix if present.
                target = os.readlink(full_path)
                if target.startswith(old_prefix):
                    new_target = os.path.join(new_prefix, target[len(old_prefix)+1:].lstrip('/'))
                    # Remove the old link and write a new one.
                    os.remove(full_path)
                    os.symlink(new_target, full_path)


# package {id, name} + repo -> package id
def get_package_id(pkg_str, repo_packages, repo_path):
    if PackageId.is_id(pkg_str):
        return pkg_str
    else:
        ids = list(pkg_id for pkg_id in repo_packages if pkg_id.name == pkg_str)
        if len(ids) == 0:
            print("No package with name {0} in repository {1}".format(pkg_str, repo_path))
            sys.exit(1)
        elif len(ids) > 1:
            print(
                "Multiple packages for name {} in repository ".format(pkg_str) +
                "Only one package of a name may be present when " +
                "using a name rather than id.")
            sys.exit(1)
        return ids[0]


def clean():
    # Run a docker container to remove src/ and result/
    cmd = DockerCmd()
    cmd.volumes = {
        abspath(""): "/pkg/:rw",
    }
    cmd.container = "ubuntu:14.04"
    cmd.run(["rm", "-rf", "/pkg/src", "/pkg/result"])


def main():
    arguments = docopt(__doc__, version="mkpanda {}".format(pkgpanda.build.constants.version))

    # Load the repository
    repo_path = os.path.normpath(os.path.expanduser(arguments['--repository-path']))
    repository = Repository(repo_path)
    repo_packages = set(map(PackageId, repository.list()))

    # Repository management commands.
    if arguments['add']:
        # Extract Package Id (Filename must be path/{pkg-id}.tar.xz).
        path = arguments['<package-tarball>']
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
        sys.exit(0)

    if arguments['list']:
        print_repo_list(repository.list())
        sys.exit(0)

    if arguments['remove']:
        for package in arguments['<name-or-id>']:
            pkg_id = get_package_id(package, repo_packages, repo_path)
            # TODO(cmaloney): the str() here is ugly.
            repository.remove(str(pkg_id))
        sys.exit(0)

    # Load the package build info.
    try:
        buildinfo = load_json("buildinfo.json")
    except FileNotFoundError:
        print("ERROR: Unable to find `buildinfo.json` in the current directory.")
        sys.exit(1)
    except ValueError as ex:
        print("ERROR:", ex)
        sys.exit(1)

    # Only clean in valid build locations (Why this is after buildinfo.json)
    if arguments['clean']:
        clean()
        sys.exit(1)

    # No command -> build package.

    # Build pkginfo over time, translating fields from buildinfo.
    pkginfo = {}

    # Build up the docker command arguments over time, translating fields as needed.
    cmd = DockerCmd()

    # Only fresh builds are allowed which don't overlap existing artifacts.
    if exists("result"):
        print("result folder must not exist. It will be made when the package " +
              "is built. {}".format(abspath("result")))
        sys.exit(1)

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

        bad_requires = False
        to_check = copy.deepcopy(buildinfo['requires'])
        if type(to_check) != list:
            print("`requires` in buildinfo.json must be an array of dependencies.")
            sys.exit(1)
        while to_check:
            pkg_str = to_check.pop(0)
            try:
                pkg_id = get_package_id(pkg_str, repo_packages, repo_path)
                if pkg_id in active_package_names:
                    continue

                # TODO(cmaloney): The str here is ugly.
                package = repository.load(str(pkg_id))

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

    # Copy over environment settings
    if 'environment' in buildinfo:
        pkginfo['environment'] = buildinfo['environment']

    # Activate the packages so that we have a proper path, environment
    # variables.
    # TODO(cmaloney): RAII type thing for temproary directory so if we
    # don't get all the way through things will be cleaned up?
    install = Install(install_dir, None, False, True)
    install.activate(repository, active_packages)
    # Rewrite all the symlinks inside the active path because we will
    # be mounting the folder into a docker container, and the absolute
    # paths to the packages will change.
    # TODO(cmaloney): This isn't very clean, it would be much nicer to
    # just run pkgpanda inside the package.
    rewrite_symlinks(install_dir, repo_path, "/opt/mesosphere/packages/")

    print("Fetching sources")
    # Clone the repositories, apply patches as needed using the patch utilities
    checkout_ids = checkout_source(sources)

    # Add the sha1sum of the buildinfo.json + build file to the build ids
    build_ids = {"sources": checkout_ids}
    build_ids['buildinfo'] = sha1("buildinfo.json")
    build_ids['build'] = sha1("build")

    # Generate the package id (upstream sha1sum + build-number)
    version_base = hash_checkout(build_ids)

    # TODO(cmaloney): If there is already a build / we've been told to build an id
    # greater than last append the build id.
    version = None
    if "version_extra" in buildinfo:
        version = "{0}-{1}".format(buildinfo["version_extra"], version_base)
    else:
        version = version_base

    docker_name = buildinfo.get('docker', 'ubuntu:14.04')
    if 'docker' in buildinfo:
        print("WARNING: Specifying docker explicitly shold be avoided.")
        print("This option will be removed once enough of the dependencies " +
              "are in pkgpanda form that everything can just use pkgpanda " +
              "dependencies.")
    cmd.container = docker_name

    # TODO(cmaloney): Mount and run a wrapper script that installs
    # dependencies.

    pkg_id = PackageId.from_parts(buildinfo['name'], version)

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

    # Bundle the artifacts into the pkgpanda package
    pkg_path = abspath("{}.tar.xz".format(pkg_id))
    make_tar(pkg_path, "result")
    print("Package built, available at {}".format(pkg_path))
    sys.exit(0)


if __name__ == "__main__":
    main()
