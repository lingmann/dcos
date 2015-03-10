
"""Panda package builder

Reads a buildinfo file, uses it to assemble the sources and determine the
package version, then builds the package in an isolated environment along with
the necessary dependencies.

Usage:
  mkpanda
"""

import sys
from os import mkdir
from os.path import abspath, exists
from shutil import copyfile
from subprocess import CalledProcessError, check_call

import pkgpanda.build.constants
from docopt import docopt
from pkgpanda import PackageId
from pkgpanda.build import checkout_source, hash_checkout, sha1
from pkgpanda.exceptions import ValidationError
from pkgpanda.util import load_json, write_json


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


def main():
    docopt(__doc__, version="mkpanda {}".format(pkgpanda.build.constants.version))

    # Load the package build info
    try:
        buildinfo = load_json("buildinfo.json")
    except FileNotFoundError:
        print("ERROR: Unable to find `buildinfo.json` in the current directory.")
        exit(-1)

    # Don't build into an already existing result, will make non-reproducible builds.
    if exists("result"):
        print("result folder must not exist. It will be made when the package " +
              "is built. {}".format(abspath("result")))

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
    # TODO(cmaloney): Fill pkginfo with useful data.
    pkginfo = {}
    if 'requires' in buildinfo:
        pkginfo['requires'] = buildinfo['requires']
        # TODO(cmaloney): Validate every requires is a valid package name
        # or package id.q
        print("WARNING: requires are not currently installed to the build " +
              "environment")

    write_json("result/pkginfo.json", pkginfo)

    cmd = DockerCmd()
    cmd.container = docker_name
    # TOOD(cmaloney): Disallow writing to well known files and directories?
    # Source we checked out
    cmd.volumes = {
        # TODO(cmaloney): src should be read only...
        abspath("src"): "/pkg/src:rw",
        # The build script
        abspath("build"): "/pkg/build:ro",
        # Getting the result out
        abspath("result"): "/opt/mesosphere/packages/{}:rw".format(pkg_id)
        # TODO(cmaloney): Install Dependencies, mount in well known files and dirs
        # Info about the package
        }
    cmd.environment = {
        "PKG_VERSION": version,
        "PKG_NAME": buildinfo['name'],
        "PKG_ID": pkg_id,
        "PKG_PATH": "/opt/mesosphere/packages/{}".format(pkg_id)
    }

    try:
        cmd.run(["/bin/bash", "-e", "/pkg/build"])
    except CalledProcessError as ex:
        print("ERROR: docker exited non-zero: {}".format(ex.returncode))
        print("Command: {}".format(' '.join(ex.cmd)))
        sys.exit(1)

    print("Building package tarball")

    # TODO(cmaloney)  build info should be copied in here but can't really
    # because of docker and crazy folder root permissions...

    # Bundle the artifacts into the pkgpanda package
    pkg_path = abspath("{}.tar.xz".format(pkg_id))
    check_call(["tar", "--numeric-owner", "--owner=0", "--group=0",
                "-cJf", pkg_path, "-C", "result", "."])
    print("Package built, available at {}".format(pkg_path))
    sys.exit(0)


if __name__ == "__main__":
    main()
