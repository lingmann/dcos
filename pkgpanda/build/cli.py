"""Panda package builder

Reads a buildinfo file, uses it to assemble the sources and determine the
package version, then builds the package in an isolated environment along with
the necessary dependencies.

Usage:
  mkpanda [--repository-url=<repository_url>]
  mkpanda tree [--mkbootstrap] [--repository-url=<repository_url>] [<variant>]
  mkpanda clean
"""

import copy
import json
import os.path
import shutil
import sys
import tempfile
from os import getcwd, mkdir, umask
from os.path import abspath, basename, exists
from subprocess import CalledProcessError, check_call, check_output

from docopt import docopt

import pkgpanda.build.constants
from pkgpanda import expand_require as expand_require_exceptions
from pkgpanda import Install, PackageId, Repository
from pkgpanda.build import checkout_sources, fetch_sources, hash_checkout, sha1
from pkgpanda.cli import add_to_repository
from pkgpanda.constants import RESERVED_UNIT_NAMES
from pkgpanda.exceptions import FetchError, PackageError, ValidationError
from pkgpanda.util import (check_forbidden_services, download, load_json, load_string, make_file, make_tar,
                           rewrite_symlinks, write_json, write_string)


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


def expand_require(require):
    try:
        return expand_require_exceptions(require)
    except ValidationError as ex:
        print("ERROR:", ex)
        sys.exit(1)


def get_docker_id(docker_name):
    return check_output(["docker", "inspect", "-f", "{{ .Id }}", docker_name]).decode('utf-8').strip()


def clean():
    # Run a docker container to remove src/ and result/
    cmd = DockerCmd()
    cmd.volumes = {
        abspath(""): "/pkg/:rw",
    }
    cmd.container = "ubuntu:14.04.4"
    cmd.run(["rm", "-rf", "/pkg/src", "/pkg/result"])


def main():
    arguments = docopt(__doc__, version="mkpanda {}".format(pkgpanda.build.constants.version))
    umask(0o022)

    # Make a local repository for build dependencies
    if arguments['tree']:
        build_tree(arguments['--mkbootstrap'], arguments['--repository-url'], arguments['<variant>'])
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
    pkg_dict = build_package_variants(name, arguments['--repository-url'])

    print("Package variants available as:")
    for k, v in pkg_dict.items():
        if k is None:
            k = "<default>"
        print(k + ':' + v)

    sys.exit(0)


def last_build_filename(variant):
    return "cache/" + ((variant + '.') if variant else "") + "latest"


def load_optional_json(filename):
    # Load the package build info.
    try:
        return load_json(filename)
    except FileNotFoundError:
        # not existing -> empty dictionary / no specified values.
        return {}
    except ValueError as ex:
        print("ERROR:", ex)
        sys.exit(1)


def load_config_variant(directory, variant, extension):
    assert directory[-1] != '/'
    filename = extension
    if variant:
        filename = variant + '.' + filename
    return load_optional_json(directory + '/' + filename)


def load_buildinfo(path, variant):
    return load_config_variant(path, variant, 'buildinfo.json')


def find_packages_fs():
    # Treat the current directory as the base of a repository of packages.
    # The packages are in folders, each containing a buildinfo.json, build.
    # Load all the requires out of all the buildinfo.json variants and return
    # them.
    start_dir = os.getcwd()

    packages = dict()
    for name in os.listdir():
        if os.path.isdir(name):
            if not os.path.exists(os.path.join(name, "build")):
                continue

            def get_requires(variant):
                buildinfo = load_buildinfo(os.getcwd(), variant)
                return {
                    'requires': buildinfo.get('requires', list())
                }

            os.chdir(start_dir + '/' + name)
            variant_requires = for_each_variant(get_requires, "buildinfo.json", [])
            os.chdir(start_dir)

            for variant, requires in variant_requires.items():
                packages[(name, variant)] = requires

    return packages


def make_bootstrap_tarball(packages, variant, repository_url):
    # Convert filenames to package ids
    pkg_ids = list()
    for pkg_path in packages:
        # Get the package id from the given package path
        filename = os.path.basename(pkg_path)
        if not filename.endswith(".tar.xz"):
            print("ERROR: Packages must be packaged / end with .tar.xz")
            sys.exit(1)
        pkg_id = filename[:-len(".tar.xz")]
        pkg_ids.append(pkg_id)

    # Filename is output_name.<sha-1>.{active.json|.bootstrap.tar.xz}
    bootstrap_id = hash_checkout(pkg_ids)
    latest_name = "bootstrap.latest"
    if variant:
        latest_name = variant + "." + latest_name

    output_name = bootstrap_id + '.'

    # bootstrap tarball = <sha1 of packages in tarball>.bootstrap.tar.xz
    bootstrap_name = "{}bootstrap.tar.xz".format(output_name)
    active_name = "{}active.json".format(output_name)

    def mark_latest():
        # Ensure latest is always written
        write_string(latest_name, bootstrap_id)

        print("bootstrap: {}".format(bootstrap_name))
        print("active: {}".format(active_name))
        print("latest: {}".format(latest_name))
        return bootstrap_name

    if (os.path.exists(bootstrap_name)):
        print("Bootstrap already up to date, not recreating")
        return mark_latest()

    # Try downloading.
    if repository_url:
        tmp_bootstrap = bootstrap_name + '.tmp'
        tmp_active = active_name + '.tmp'
        try:
            repository_url = repository_url.rstrip('/')
            bootstrap_url = repository_url + '/bootstrap/' + bootstrap_name
            active_url = repository_url + '/bootstrap/' + active_name
            print("Attempting to download", bootstrap_name, "from", bootstrap_url)
            # Normalize to no trailing slash for repository_url
            download(tmp_bootstrap, bootstrap_url)
            print("Attempting to download", active_name, "from", active_url)
            download(tmp_active, active_url)

            # Move into place
            os.rename(tmp_bootstrap, bootstrap_name)
            os.rename(tmp_active, active_name)

            print("Bootstrap already up to date, Not recreating. Downloaded from repository-url.")
            return mark_latest()
        except FetchError:
            try:
                os.remove(tmp_bootstrap)
            except:
                pass
            try:
                os.remove(tmp_active)
            except:
                pass

            # Fall out and do the build since the command errored.
            print("Unable to download from cache. Building.")

    print("Creating bootstrap tarball for variant {}".format(variant))

    work_dir = tempfile.mkdtemp(prefix='mkpanda_bootstrap_tmp')

    def make_abs(path):
        return os.path.join(work_dir, path)

    pkgpanda_root = make_abs("opt/mesosphere")
    repository = pkgpanda.Repository(os.path.join(pkgpanda_root, "packages"))

    # Fetch all the packages to the root
    for pkg_path in packages:
        filename = os.path.basename(pkg_path)
        pkg_id = filename[:-len(".tar.xz")]

        def local_fetcher(id, target):
            shutil.unpack_archive(pkg_path, target, "gztar")
        repository.add(local_fetcher, pkg_id, False)

    # Activate the packages inside the repository.
    # Do generate dcos.target.wants inside the root so that we don't
    # try messing with /etc/systemd/system.
    install = pkgpanda.Install(pkgpanda_root, None, True, False, True, True, True)
    install.activate(repository.load_packages(pkg_ids))

    # Mark the tarball as a bootstrap tarball/filesystem so that
    # dcos-setup.service will fire.
    make_file(make_abs("opt/mesosphere/bootstrap"))

    # Write out an active.json for the bootstrap tarball
    write_json(active_name, pkg_ids)

    # Rewrite all the symlinks to point to /opt/mesosphere
    rewrite_symlinks(work_dir, work_dir, "/")

    make_tar(bootstrap_name, pkgpanda_root)

    shutil.rmtree(work_dir)

    # Update latest last so that we don't ever use partially-built things.
    write_string(latest_name, bootstrap_id)

    print("Built bootstrap")
    return mark_latest()


ALLOWED_TREEINFO_KEYS = {'exclude', 'variants', 'core_package_list'}


def get_tree_package_tuples(tree_variant, possible_packages, package_requires):
    treeinfo = load_config_variant(os.getcwd(), tree_variant, 'treeinfo.json')

    if treeinfo.keys() > ALLOWED_TREEINFO_KEYS:
        print("treeinfo can only include the keys {}. Found {}".format(ALLOWED_TREEINFO_KEYS, treeinfo.keys()))
        sys.exit(1)

    core_package_list = treeinfo.get('core_package_list', None)
    if core_package_list is not None and not isinstance(core_package_list, list):
        print("ERROR: core_package_list must either be null meaning don't use "
              "or a list of the core packages to include (dependencies are automatically picked up).")
        sys.exit(1)

    excludes = treeinfo.get('exclude', list())
    if not isinstance(excludes, list):
        print("ERROR: treeinfo exclude must be a list of packages to exclude.")
        sys.exit(1)

    for exclude in excludes:
        if not isinstance(exclude, str):
            print("ERROR: Excludes should be a list of strings of package names.",
                  "Found a", type(exclude), "with the value: {}".format(exclude))
            sys.exit(1)

    # Validate core_package_lists is formatted as expected, doesn't contain
    # any of exclude.
    if core_package_list is not None:
        for name in core_package_list:
            if not isinstance(name, str):
                print("ERROR: core_package_list should be a list of package name "
                      "strings, found a", type(name), "with the value: {}".format(name))
                sys.exit(1)

            if name in excludes:
                print("ERROR: Package found in both exclude and core_package_list: {}".format(name))
                sys.exit(1)

    # List of mandatory package variants to include in the buildinfo.
    variants = treeinfo.get('variants', dict())

    if not isinstance(variants, dict):
        print("ERROR: treeinfo variants must be a dictionary of package name to variant name.")
        sys.exit(1)

    # Generate the list of package paths of all packages variants which were
    # included and excluding those removed.
    package_names = set()
    package_tuples = set()

    def include_package(name, variant):
        if name in excludes:
            print("ERROR: package", name, "is in excludes but was needed as a "
                  "dependency of an included package.")
            sys.exit(1)

        if name not in possible_packages or variant not in possible_packages[name]:
            print("ERROR: package", name, "variant", variant, " is needed but is "
                  "not in the set of built packages but is needed (explicitly "
                  "requested or as a requires)")
            sys.exit(1)

        # Allow adding duplicates. There is a check that we don't have a repeat
        # of the same package name with different variants, so we can ignore the
        # variant name.
        if name in package_names:
            pass
        package_names.add(name)
        package_tuples.add((name, variant))

    for name in possible_packages.keys():
        if core_package_list is not None:
            assert isinstance(core_package_list, list)

            # Skip over packages not in the core package list. We'll add requires
            # later when resolving / validating the requires graph.
            if name not in core_package_list:
                continue

        if name in excludes:
            continue

        # Sanity check
        assert name not in package_names

        include_package(name, variants.get(name))

    # Validate that all mandatory package variants are included
    for name, variant in variants.items():
        if (name, variant) not in package_tuples:
            print("ERROR: package", name, "is supposed to have variant",
                  variant, "included in the tree according",
                  "to the treeinfo.json, but the no such package (let alone",
                  "variant) was found")
            sys.exit(1)

    # Validate that all required packages are included. This implicitly
    # validates that no two packages include conflicting variants. If they
    # included different variants, only one of the variant could be included
    # because we iterate over the list of packages once so only one variant
    # could get included. If another variant is asked for in the requires,
    # then that variant won't be included and we'll error.
    to_visit = list(package_tuples)
    while len(to_visit) > 0:
        name, variant = to_visit.pop()
        requires = package_requires[(name, variant)]['requires']
        for require in requires:
            require_tuple = expand_require(require)
            if require_tuple not in package_tuples:
                if core_package_list is not None:
                    # TODO(cmaloney): Include the context information of the
                    # else case when printing out the info.
                    include_package(require_tuple[0], require_tuple[1])
                    to_visit.append(require_tuple)
                else:
                    print("ERROR: Package", name, "requires", require_tuple[0],
                          "variant", require_tuple[1], "but that is not in the set",
                          "of packages listed for the tree", tree_variant, ":", package_tuples)
                    sys.exit(1)

    # Integrity / programming check excludes were all excluded.
    for exclude in excludes:
        assert exclude not in package_names
    return package_tuples


def build_tree(mkbootstrap, repository_url, tree_variant=None):
    packages = find_packages_fs()

    # Turn packages into the possible_packages dictionary
    possible_packages = dict()
    for name, variant in packages.keys():
        possible_packages.setdefault(name, set())
        possible_packages[name].add(variant)

    # Check the requires and figure out a feasible build order
    # depth-first traverse the dependency tree, yielding when we reach a
    # leaf or all the dependencies of package have been built. If we get
    # back to a node without all it's dependencies built, error (likely
    # circular).
    # TODO(cmaloney): Add support for circular dependencies. They are doable
    # long as there is a pre-built version of enough of the packages.

    # TODO(cmaloney): Make it so when we're building a treeinfo which has a
    # explicit package list we don't build all the other packages.
    build_order = list()
    visited = set()
    built = set()

    def visit(pkg_tuple):
        # Visit the node for the first (and only time). Finding a node again
        # means a cycle and should be detected at caller.

        assert isinstance(pkg_tuple, tuple)

        assert pkg_tuple not in visited
        visited.add(pkg_tuple)

        name = pkg_tuple[0]

        # Ensure all dependencies are built
        for require in sorted(packages[pkg_tuple].get("requires", list())):
            require_tuple = expand_require(require)
            if require_tuple in built:
                continue
            if require_tuple in visited:
                print("ERROR: Circular dependency. Circular link {0} -> {1}".format(name, require_tuple))
                raise ValueError
                sys.exit(1)

            if PackageId.is_id(require_tuple[0]):
                print("ERROR: Depending on a specific package id is not "
                      "supported. Package", name, "depends on", require_tuple)
                sys.exit(1)

            if require_tuple not in packages:
                print("ERROR: Package {0} require {1} not buildable from tree.".format(name, require_tuple))
                sys.exit(1)

            visit(require_tuple)

        build_order.append(name)
        built.add(pkg_tuple)

    # Can't compare none to string, so expand none -> "true" / "false", then put
    # the string in a field after "" if none, the string if not.
    def key_func(elem):
        return elem[0], elem[1] is None,  elem[1] or ""

    # Build everything if no variant is given
    if tree_variant is None:
        # Since there may be multiple isolated dependency trees, iterate through
        # all packages to find them all.
        for pkg_tuple in sorted(packages.keys(), key=key_func):
            if pkg_tuple in visited:
                continue
            visit(pkg_tuple)
    else:
        # Build all the things needed for this variant and only this variant
        for pkg_tuple in sorted(get_tree_package_tuples(tree_variant, possible_packages, packages), key=key_func):
            if pkg_tuple in visited:
                continue
            visit(pkg_tuple)

    built_packages = dict()
    start_dir = os.getcwd()
    for name in build_order:
        print("Building: {}".format(name))

        # Run the build, store the built package path for later use.
        os.chdir(start_dir + '/' + name)
        # TODO(cmaloney): Only build the requested variants, rather than all variants.
        built_packages[name] = build_package_variants(name, repository_url)
        os.chdir(start_dir)

    def make_bootstrap(bootstrap_variant):
        print("Making bootstrap variant:", bootstrap_variant or "<default>")
        package_paths = list()
        for name, variant in get_tree_package_tuples(bootstrap_variant, possible_packages, packages):
            package_paths.append(built_packages[name][variant])

        if mkbootstrap:
            return make_bootstrap_tarball(list(sorted(package_paths)), bootstrap_variant, repository_url)

    # Make sure all treeinfos are satisfied and generate their bootstrap
    # tarballs if requested.
    # TODO(cmaloney): Allow distinguishing between "build all" and "build the default one".
    if tree_variant is None:
        return for_each_variant(make_bootstrap, "treeinfo.json", [])
    else:
        return {
            tree_variant: make_bootstrap(tree_variant)
        }


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


def for_each_variant(fn, extension, extra_args):
    extension = '.' + extension
    # Find all the files which end in the extension. Remove the extension to get just the variant
    variants = [sorted(filename[:-len(extension)] for filename in os.listdir() if filename.endswith(extension))]

    # Do all named variants
    results = dict()
    for variant in variants:
        results[variant] = fn(variant, *extra_args)

    # Always do the base variant
    results[None] = fn(None, *extra_args)

    return results


# Find all build variants and build them
def build_package_variants(name, repository_url):
    return for_each_variant(build, "buildinfo.json", [name, repository_url])


def build(variant, name, repository_url):
    print("Building package {} variant {}".format(name, variant or "<default>"))
    tmpdir = tempfile.TemporaryDirectory(prefix="pkgpanda_repo")
    repository = Repository(tmpdir.name)

    # Build pkginfo over time, translating fields from buildinfo.
    pkginfo = {}

    # Build up the docker command arguments over time, translating fields as needed.
    cmd = DockerCmd()

    buildinfo = load_buildinfo(os.getcwd(), variant)

    if 'name' in buildinfo:
        print("ERROR: 'name' is not allowed in buildinfo.json, it is " +
              "implicitly the name of the folder containing the buildinfo.json")
        sys.exit(1)

    # Make sure build_script is only set on variants
    if 'build_script' in buildinfo and variant is None:
        print("ERROR: build_script can only be set on package variants")
        sys.exit(1)

    # Convert single_source -> sources
    try:
        sources = expand_single_source_alias(name, buildinfo)
    except ValidationError as ex:
        print("ERROR: Invalid buildinfo.json for package:", ex)
        sys.exit(1)

    # Save the final sources back into buildinfo so it gets written into
    # buildinfo.json. This also means buildinfo.json is always expanded form.
    buildinfo['sources'] = sources

    print("Fetching sources")
    # Clone the repositories, apply patches as needed using the patch utilities.
    try:
        checkout_ids = fetch_sources(sources)
    except ValidationError as ex:
        print("ERROR: Validation error when fetching sources for package:", ex)
        sys.exit(1)

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

    # Add the "extra" folder inside the package as an additional source if it
    # exists
    if os.path.exists('extra'):
        extra_id = pkgpanda.build.hash_folder('extra')
        build_ids['extra_source'] = extra_id
        buildinfo['extra_source'] = extra_id

    # Figure out the docker name.
    docker_name = buildinfo.get('docker', 'ubuntu:14.04.4')
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
    active_package_ids = set()
    active_package_variants = dict()
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
            requires_info = to_check.pop(0)
            requires_name, requires_variant = expand_require(requires_info)

            if requires_name in active_package_variants:
                # TODO(cmaloney): If one package depends on the <default>
                # variant of a package and 1+ others depends on a non-<default>
                # variant then update the dependency to the non-default variant
                # rather than erroring.
                if requires_variant != active_package_variants[requires_name]:
                    # TODO(cmaloney): Make this contain the chains of
                    # dependencies which contain the conflicting packages.
                    # a -> b -> c -> d {foo}
                    # e {bar} -> d {baz}
                    print("ERROR: Dependncy on multiple variants of the same",
                          "package", requires_name, ". variants:", requires_variant,
                          active_package_variants[requires_name])
                    sys.exit(1)

                # The variant has package {requires_name, variant} already is a
                # dependency, don't process it again / move on to the next.
                continue

            active_package_variants[requires_name] = requires_variant

            # Figure out the last build of the dependency, add that as the
            # fully expanded dependency.
            pkg_dir = '../' + requires_name
            last_build = pkg_dir + '/' + last_build_filename(requires_variant)
            if not os.path.exists(last_build):
                print("ERROR: No last build file found for dependency",
                      requires_name, "variant", requires_variant,
                      "Rebuild the dependency")
                sys.exit(1)

            try:
                pkg_id_str = load_string(last_build)
                auto_deps.add(pkg_id_str)
                pkg_buildinfo = load_buildinfo(pkg_dir, requires_variant)
                pkg_requires = pkg_buildinfo.get('requires', list())
                pkg_path = repository.package_path(pkg_id_str)
                pkg_tar = pkg_id_str + '.tar.xz'
                if not os.path.exists(pkg_dir + '/' + pkg_tar):
                    print("ERROR: The build tarball", pkg_tar, "refered to by",
                          "the last_build file of the dependency",
                          requires_name, "variant", requires_variant, "doesn't",
                          "exist. Rebuild the dependency.")
                    sys.exit(1)

                active_package_ids.add(pkg_id_str)

                # Mount the package into the docker container.
                cmd.volumes[pkg_path] = "/opt/mesosphere/packages/{}:ro".format(pkg_id_str)
                os.makedirs(os.path.join(install_dir, "packages/{}".format(pkg_id_str)))

                # Add the dependencies of the package to the set which will be
                # activated.
                # TODO(cmaloney): All these 'transitive' dependencies shouldn't
                # be available to the package being built, only what depends on
                # them directly.
                to_check += pkg_requires
            except ValidationError as ex:
                print("ERROR validating package needed as dependency {0}: {1}".format(requires_name, ex))
                bad_requires = True
            except PackageError as ex:
                print("ERROR loading package needed as dependency {0}: {1}".format(requires_name, ex))
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

    # Save the package name and variant. The variant is used when installing
    # packages to validate dependencies.
    buildinfo['name'] = name
    buildinfo['variant'] = variant

    # If the package is already built, don't do anything.
    pkg_path = abspath("{}.tar.xz".format(pkg_id))

    # Done if it exists locally
    if exists(pkg_path):
        print("Package up to date. Not re-building.")

        # TODO(cmaloney): Updating / filling last_build should be moved out of
        # the build function.
        check_call(["mkdir", "-p", "cache"])
        write_string(last_build_filename(variant), str(pkg_id))

        return pkg_path

    # Try downloading.
    if repository_url:
        tmp_filename = pkg_path + '.tmp'
        try:
            url = repository_url + '/packages/{0}/{1}.tar.xz'.format(pkg_id.name, str(pkg_id))
            print("Attempting to download", pkg_id, "from", url)
            # Normalize to no trailing slash for repository_url
            repository_url = repository_url.rstrip('/')
            download(tmp_filename, url)
            os.rename(tmp_filename, pkg_path)

            print("Package up to date. Not re-building. Downloaded from repository-url.")
            # TODO(cmaloney): Updating / filling last_build should be moved out of
            # the build function.
            check_call(["mkdir", "-p", "cache"])
            write_string(last_build_filename(variant), str(pkg_id))
            return pkg_path
        except FetchError:
            try:
                os.remove(tmp_filename)
            except:
                pass

            # Fall out and do the build since the command errored.
            print("Unable to download from cache. Proceeding to build")

    print("Building package {} with buildinfo: {}".format(
        pkg_id,
        json.dumps(buildinfo, indent=2, sort_keys=True)))

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
    install = Install(install_dir, None, True, False, True, True)
    install.activate(active_packages)
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
        abspath(buildinfo.get('build_script', 'build')): "/pkg/build:ro",
        # Getting the result out
        abspath("result"): "/opt/mesosphere/packages/{}:rw".format(pkg_id),
        install_dir: "/opt/mesosphere:ro"
    })

    if os.path.exists("extra"):
        cmd.volumes[abspath("extra")] = "/pkg/extra:ro"

    cmd.environment = {
        "PKG_VERSION": version,
        "PKG_NAME": name,
        "PKG_ID": pkg_id,
        "PKG_PATH": "/opt/mesosphere/packages/{}".format(pkg_id),
        "PKG_VARIANT": variant if variant is not None else "<default>"
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
    write_string(last_build_filename(variant), str(pkg_id))

    # Check for forbidden services before packaging the tarball:
    try:
        check_forbidden_services(abspath("result"), RESERVED_UNIT_NAMES)
    except ValidationError as e:
        print("Package validation failed: {}".format(e))
        sys.exit(1)

    # Bundle the artifacts into the pkgpanda package
    tmp_name = pkg_path + "-tmp.tar.xz"
    make_tar(tmp_name, "result")
    os.rename(tmp_name, pkg_path)
    print("Package built.")
    return pkg_path


if __name__ == "__main__":
    main()
