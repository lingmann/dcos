
"""Panda package builder

Reads a buildinfo file, uses it to assemble the sources and determine the
package version, then builds the package in an isolated environment along with
the necessary dependencies.

Usage:
  mkpanda
"""

import binascii
import hashlib
import sys
from errno import EEXIST
from os import mkdir
from os.path import abspath
from shutil import copyfile
from subprocess import check_call

import package.build.constants
from docopt import docopt
from package import PackageId
from package.build import checkout_source
from package.exceptions import ValidationError
from package.util import load_json, write_json

sha1 = hashlib.sha1()


def hash_checkout(item):
    def hash_str(s):
        sha1 = hashlib.sha1()
        sha1.update(s.encode('utf-8'))
        return binascii.hexlify(sha1.digest()).decode('ascii')

    def hash_dict(d):
        item_hashes = []
        for k in sorted(d.keys()):
            assert isinstance(k, str)
            item_hashes.append("{0}={1}".format(k, hash_checkout(d[k])))
        return hash_str(",".join(item_hashes))

    if isinstance(item, str) or isinstance(item, bytes):
        return hash_str(item)
    elif isinstance(item, dict):
        return hash_dict(item)
    else:
        raise NotImplementedError()


def main():
    docopt(__doc__, version="mkpanda {}".format(package.build.constants.version))

    # Load the package build info
    try:
        buildinfo = load_json("buildinfo.json")
    except FileNotFoundError:
        print("ERROR: Unable to find `buildinfo.json` in the current directory.")
        exit(-1)

    # TODO(cmaloney): one buildinfo -> multiple packages builds.
    # TODO(cmaloney): allow a shorthand for single source packages.
    if "sources" not in buildinfo:
        raise ValidationError("Must specify at least one source to build package from.")

    print("Fetching sources")
    # Clone the repositories, apply patches as needed using the patch utilities
    checkout_ids = checkout_source(buildinfo["sources"])

    # Generate the package id (upstream sha1sum + build-number)
    version_base = hash_checkout(checkout_ids)
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

    try:
        mkdir("result")
    except OSError as ex:
        if ex.errno != EEXIST:
            raise

    # Copy the build info to the resulting tarball
    copyfile("src/build_ids.json", "result/build_ids.json")
    copyfile("buildinfo.json", "result/buildinfo.json")
    # TODO(cmaloney): Fill pkginfo with useful data.
    write_json("result/pkginfo.json", {})

    check_call([
        "docker",
        "run",
        # TOOD(cmaloney): Disallow writing to well known files and directories?
        # Source we checked out
        # TODO(cmaloney): src should be read only...
        "-v", "{}:/pkg/src:rw".format(abspath("src")),
        # The build script
        "-v", "{}:/pkg/build:ro".format(abspath("build")),

        # Getting the result out
        "-v", "{0}:/opt/mesosphere/packages/{1}".format(abspath("result"), pkg_id),
        # TODO(cmaloney): Install Dependencies, mount in well known files and dirs
        # Info about the package
        "-e", "PKG_VERSION={}".format(version),
        "-e", "PKG_NAME={}".format(buildinfo['name']),
        "-e", "PKG_ID={}".format(pkg_id),
        "-e", "PKG_PATH={}".format("/opt/mesosphere/packages/{}".format(pkg_id)),

        # Build environment
        docker_name,

        # Run the build script
        "/pkg/build"])

    print("Building package tarball")

    # TODO(cmaloney)  build info should be copied in here but can't really
    # because of docker and crazy folder root permissions...

    # Bundle the artifacts into the pkgpanda package
    pkg_path = abspath("{}.tar.xz".format(pkg_id))
    check_call(["tar", "-cJf", pkg_path, "-C", "result", "."])
    print("Package built, available at {}".format(pkg_path))
    sys.exit(0)


if __name__ == "__main__":
    main()
