"""Panda package builder

Reads a buildinfo file, uses it to assemble the sources and determine the
package version, then builds the package in an isolated environment along with
the necessary dependencies.

Usage:
  mkpanda [--repository-url=<repository_url>]
  mkpanda tree [--mkbootstrap] [--repository-url=<repository_url>]
  mkpanda clean
"""

import copy
import os.path
import sys
import tempfile
from os import getcwd, mkdir, umask
from os.path import abspath, basename, exists
from subprocess import CalledProcessError, check_call, check_output

import pkgpanda.build.constants
from docopt import docopt
from pkgpanda import Install, PackageId, Repository
from pkgpanda.build import checkout_sources, fetch_sources, hash_checkout, make_bootstrap_tarball, sha1
from pkgpanda.cli import add_to_repository
from pkgpanda.exceptions import PackageError, ValidationError
from pkgpanda.util import load_json, load_string, make_tar, rewrite_symlinks, write_json, write_string


class DockerCmd:

    def __init__(self):
        self.volumes = dict()
        self.environment = dict()
        self.container = str()

    def run(self, cmd):
        docker = ["docker", "run"]
        for host_path, container_path in self.volumes.items():
            docker += ["-v", "{0}:{1}".format(host_path, container_path)]

        for k, v in self.environment.items():
            docker += ["-e", "{0}={1}".format(k, v)]

        docker.append(self.container)
        docker += cmd
        check_call(docker)


def get_docker_id(docker_name):
    return check_output(["docker", "inspect", "-f", "{{ .Id }}", docker_name]).decode('utf-8').strip()


# package {id, name} + repo -> package id
def get_package_id(repository, pkg_str):
    if PackageId.is_id(pkg_str):
        return pkg_str
    else:
        ids = repository.get_ids(pkg_str)
        if len(ids) == 0:
            return None
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


def main():
    arguments = docopt(__doc__, version="mkpanda {}".format(pkgpanda.build.constants.version))
    umask(0o022)

    # Make a local repository for build dependencies
    if arguments['tree']:
        build_tree(arguments['--mkbootstrap'], arguments['--repository-url'])
        sys.exit(0)

    # Check for the 'build' file to verify this is a valid package directory.
    if not exists("build"):
        print("Not a valid package folder. No 'build' file.")
        sys.exit(1)

    # Package name is the folder name.
    name = basename(getcwd())

    # Only clean in valid build locations (Why this is after buildinfo.json)
    if arguments['clean']:
        clean()
        sys.exit(0)

    # No command -> build package.
    pkg_path = build(
        name,
        arguments['--repository-url'])

    print("Package available at: {}".format(pkg_path))

    sys.exit(0)


def load_buildinfo(path):
    # Load the package build info.
    try:
        return load_json(os.path.join(path, "buildinfo.json"))
    except FileNotFoundError:
        # All fields in buildinfo are optional.
        return {}
    except ValueError as ex:
        print("ERROR:", ex)
        sys.exit(1)


def find_packages_fs():
    # Treat the current directory as the base of a repository of packages.
    # The packages are in folders, each containing a buildinfo.json, build.
    # Load all the buildinfos, topo-sort the dependencies, then build if/when
    # needed (Check build_ids.json vs. new pull).
    packages = dict()
    for name in os.listdir():
        if os.path.isdir(name):
            if not os.path.exists(os.path.join(name, "build")):
                continue
            buildinfo = load_buildinfo(name)
            packages[name] = {'requires': buildinfo.get('requires', list())}
    return packages


def load_treeinfo(name, working_on=set()):
    # Open the treeinfo, read out the packages that will make up the tree.
    # For each of those packages, load the requires out of the buildinfo.json in
    # folder if one exists.
    working_on.add(name)

    treeinfo = load_json('{}.treeinfo.json'.format(name))
    if 'packages' not in treeinfo:
        treeinfo['packages'] = dict()

    def merge_treeinfo_packages(parent_name):
        if parent_name in working_on:
            # The parent instance will add all the things, so just skip it.
            return

        parent_info = load_treeinfo(parent_name, working_on)

        for name, sources in parent_info['packages'].items():
            if name in treeinfo['packages']:
                continue
            treeinfo['packages'][name] = sources

    if 'from' in treeinfo:
        from_trees = treeinfo['from']

        if type(from_trees) is str:
            merge_treeinfo_packages(from_trees)
        elif type(from_trees) is list:
            for tree in from_trees:
                merge_treeinfo_packages(tree)

    return treeinfo


def build_tree(mkbootstrap, repository_url):
    packages = find_packages_fs()

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
    for name in build_order:
        print("Building: {}".format(name))
        build_cmd = ["mkpanda"]

        # Forward the repository url to the actual build run.
        if repository_url:
            build_cmd += ['--repository-url=' + repository_url]

        # Run the build
        check_call(build_cmd, cwd=abspath(name))

        # Add the package to the set of built packages.
        # Don't auto-add since 'mkpanda' will add as needed.
        package_id = load_string(os.path.join(name, "cache/last_build"))
        pkg_path = "{0}/{1}.tar.xz".format(name, package_id)
        built_package_paths.add(pkg_path)

    # Build the tarball if requested, along with a "active.json"
    if mkbootstrap:
        # TODO(cmaloney): This does a ton of excess repeated work...
        # use the repository built during package building instead of
        # building a new one for the package tarball (just mv it).
        make_bootstrap_tarball('', list(sorted(built_package_paths)))


def expand_single_source_alias(pkg_name, buildinfo):
    if "sources" in buildinfo:
        return buildinfo["sources"]
    elif "single_source" in buildinfo:
        return {pkg_name: buildinfo["single_source"]}
    else:
        print("NOTICE: No sources specified")
        return {}


def assert_no_duplicate_keys(lhs, rhs):
    if len(lhs.keys() & rhs.keys()) != 0:
        print("ASSERTION FAILED: Duplicate keys between {} and {}".format(lhs, rhs))
        assert len(lhs.keys() & rhs.keys()) == 0


def build(name, repository_url):
    tmpdir = tempfile.TemporaryDirectory(prefix="pkgpanda_repo")
    repository = Repository(tmpdir.name)

    # Build pkginfo over time, translating fields from buildinfo.
    pkginfo = {}

    # Build up the docker command arguments over time, translating fields as needed.
    cmd = DockerCmd()

    buildinfo = load_buildinfo(os.getcwd())

    if 'name' in buildinfo:
        print("WARNING: 'name' in buildinfo is deprecated.")
        if buildinfo['name'] != name:
            print("ERROR: buildinfo name '{0}' needs to match folder name '{1}'".format(buildinfo['name'], name))
            sys.exit(1)

    # Convert single_source -> sources
    sources = None

    try:
        pkg_sources = expand_single_source_alias(name, buildinfo)
    except ValidationError as ex:
        print("ERROR: Invalid buildinfo.json for package:", ex)
        sys.exit(1)

    # If an override buildinfo is given, make sure it overrides the package
    # buildinfo sources. If no override is given, use the package buildinfo
    # sources.
    if sources:
        if sources.keys() != pkg_sources.keys():
            print("ERROR: Override buildinfo must provide the same sources as original package buildinfo")
            print("Package  buildinfo sources: {}".format(",".join(pkg_sources.keys())))
            print("Override buildinfo sources: {}".format(",".join(sources.keys())))
            sys.exit(1)
        print("Package sources overrridden as requested")
    else:
        sources = pkg_sources

    # Save the final sources back into buildinfo so it gets written into
    # buildinfo.json. This also means buildinfo.json is always expanded form.
    buildinfo['sources'] = sources

    print("Fetching sources")
    # Clone the repositories, apply patches as needed using the patch utilities.
    checkout_ids = fetch_sources(sources)

    for src_name, checkout_id in checkout_ids.items():
        # NOTE: single_source buildinfo was expanded above so the src_name is
        # always correct here.

        # Make sure we never accidentally overwrite something which might be
        # important. Fields should match if specified (And that should be
        # tested at some point). For now disallowing identical saves hassle.
        assert_no_duplicate_keys(checkout_id, buildinfo['sources'][src_name])
        buildinfo['sources'][src_name].update(checkout_id)

    # Add the sha1sum of the buildinfo.json + build file to the build ids
    build_ids = {"sources": checkout_ids}
    build_ids['build'] = sha1("build")
    build_ids['pkgpanda_version'] = pkgpanda.build.constants.version

    # Figure out the docker name.
    docker_name = buildinfo.get('docker', 'ubuntu:14.04.2')
    if 'docker' in buildinfo:
        print("WARNING: Specifying docker explicitly should be avoided.")
        print("This option will be removed once enough of the dependencies " +
              "are in pkgpanda form that everything can just use pkgpanda " +
              "dependencies.")
    cmd.container = docker_name

    # Add the id of the docker build environment to the build_ids.
    try:
        docker_id = get_docker_id(docker_name)
    except CalledProcessError:
        # docker pull the container and try again
        check_call(['docker', 'pull', docker_name])
        docker_id = get_docker_id(docker_name)

    build_ids['docker'] = docker_id

    # TODO(cmaloney): The environment variables should be generated during build
    # not live in buildinfo.json.
    build_ids['environment'] = buildinfo.get('environment', {})

    # Packages need directories inside the fake install root (otherwise docker
    # will try making the directories on a readonly filesystem), so build the
    # install root now, and make the package directories in it as we go.
    install_dir = tempfile.mkdtemp(prefix="pkgpanda-")

    active_packages = list()
    active_package_names = set()
    active_package_ids = set()
    auto_deps = set()
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
                pkg_id_str = get_package_id(repository, pkg_str)

                pkg_name = None
                pkg_requires = None

                if pkg_id_str is None:
                    if PackageId.is_id(pkg_str):
                        # Package names only ATM.
                        raise NotImplementedError()

                    # Try and add the package automatically
                    last_build = '../{}/cache/last_build'.format(pkg_str)
                    if not os.path.exists(last_build):
                        print("ERROR: No last build for dependency {}. Can't auto-add.".format(pkg_str))
                        sys.exit(1)
                    pkg_name = pkg_str
                    pkg_id_str = load_string(last_build)
                    auto_deps.add(pkg_id_str)
                    pkg_buildinfo = load_buildinfo('../{}'.format(pkg_str))
                    pkg_requires = pkg_buildinfo.get('requires', list())
                    pkg_path = repository.package_path(pkg_id_str)
                    if not os.path.exists('../{0}/{1}.tar.xz'.format(pkg_str, pkg_id_str)):
                        print("ERROR: Last build for dependency {} doesn't exist.".format(pkg_str) +
                              " Rebuild the dependency.")
                        sys.exit(1)

                    if PackageId(pkg_id_str).name in active_package_names:
                        continue
                else:

                    package = repository.load(pkg_id_str)
                    pkg_name = package.name
                    pkg_id = package.id
                    pkg_requires = package.requires
                    pkg_path = package.path
                    if PackageId(pkg_id_str).name in active_package_names:
                        continue
                    active_packages.append(package)

                active_package_ids.add(pkg_id_str)

                # Mount the package into the docker container.
                cmd.volumes[pkg_path] = "/opt/mesosphere/packages/{}:ro".format(pkg_id_str)

                os.makedirs(os.path.join(install_dir, "packages/{}".format(pkg_id_str)))

                # Mark the package as active so we don't check it again and
                # infinite loop on cycles.
                active_package_names.add(pkg_name)

                # Add the dependencies of the package to the set which will be
                # activated.
                # TODO(cmaloney): All these 'transitive' dependencies shouldn't
                # be available to the package being built, only what depends on
                # them directly.
                to_check += pkg_requires
            except ValidationError as ex:
                print("ERROR validating package needed as dependency {0}: {1}".format(pkg_str, ex))
                bad_requires = True
            except PackageError as ex:
                print("ERROR loading package needed as dependency {0}: {1}".format(pkg_str, ex))
                bad_requires = True

        if bad_requires:
            sys.exit(1)

    # Add requires to the package id, calculate the final package id.
    # NOTE: active_packages isn't fully constructed here since we lazily load
    # packages not already in the repository.
    build_ids['requires'] = list(active_package_ids)
    version_base = hash_checkout(build_ids)
    version = None
    if "version_extra" in buildinfo:
        version = "{0}-{1}".format(buildinfo["version_extra"], version_base)
    else:
        version = version_base
    pkg_id = PackageId.from_parts(name, version)

    # Save the build_ids. Useful for verify exactly what went into the
    # package build hash.
    buildinfo['build_ids'] = build_ids
    buildinfo['package_version'] = version

    # If the package is already built, don't do anything.
    pkg_path = abspath("{}.tar.xz".format(pkg_id))

    # Done if it exists locally
    if exists(pkg_path):
        print("Package up to date. Not re-building.")

        # TODO(cmaloney): Updating / filling last_build should be moved out of
        # the build function.
        check_call(["mkdir", "-p", "cache"])
        write_string("cache/last_build", str(pkg_id))

        return pkg_path

    # Try downloading.
    if repository_url:
        tmp_filename = pkg_path + '.tmp'
        try:
            print("Attempting to download", pkg_id, "from repository-url", repository_url)
            # Normalize to no trailing slash for repository_url
            repository_url = repository_url.rstrip('/')
            check_call([
                'curl',
                '-fsSL',
                '-o', tmp_filename,
                repository_url + '/packages/{0}/{1}.tar.xz'.format(pkg_id.name, str(pkg_id))])
            os.rename(tmp_filename, pkg_path)

            print("Package up to date. Not re-building. Downloaded from repository-url.")
            # TODO(cmaloney): Updating / filling last_build should be moved out of
            # the build function.
            check_call(["mkdir", "-p", "cache"])
            write_string("cache/last_build", str(pkg_id))
            return pkg_path
        except CalledProcessError as ex:
            try:
                os.remove(tmp_filename)
            except:
                pass
            # Fall out and do the build since the command errored.

    # Clean out src, result so later steps can use them freely for building.
    clean()

    # Only fresh builds are allowed which don't overlap existing artifacts.
    if exists("result"):
        print("result folder must not exist. It will be made when the package " +
              "is built. {}".format(abspath("result")))
        sys.exit(1)

    # 'mkpanda add' all implicit dependencies since we actually need to build.
    for dep in auto_deps:
        print("Auto-adding dependency: {}".format(dep))
        # NOTE: Not using the name pkg_id because that overrides the outer one.
        id_obj = PackageId(dep)
        add_to_repository(repository, '../{0}/{1}.tar.xz'.format(id_obj.name, dep))
        package = repository.load(dep)
        active_packages.append(package)

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

    print("Building package in docker")

    # TODO(cmaloney): Run as a specific non-root user, make it possible
    # for non-root to cleanup afterwards.
    # Run the build, prepping the environment as necessary.
    mkdir("result")

    # Copy the build info to the resulting tarball
    write_json("src/buildinfo.full.json", buildinfo)
    write_json("result/buildinfo.full.json", buildinfo)

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
        "PKG_NAME": name,
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
    check_call(['rm', '-rf', install_dir])

    print("Building package tarball")

    # TODO(cmaloney): Updating / filling last_build should be moved out of
    # the build function.
    check_call(["mkdir", "-p", "cache"])
    write_string("cache/last_build", str(pkg_id))

    # Bundle the artifacts into the pkgpanda package
    tmp_name = pkg_path + "-tmp.tar.xz"
    make_tar(tmp_name, "result")
    os.rename(tmp_name, pkg_path)
    print("Package built.")
    return pkg_path


if __name__ == "__main__":
    main()
