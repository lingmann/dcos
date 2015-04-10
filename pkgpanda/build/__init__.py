import binascii
import hashlib
import os.path
import pkgpanda
import shutil
import sys
import tempfile
import urllib.request
from pkgpanda.util import make_file, make_tar, rewrite_symlinks, write_json
from subprocess import check_call, check_output
from urllib.parse import urlparse

from pkgpanda.exceptions import ValidationError


def sha1(filename):
    return check_output(["sha1sum", filename]).split()[0].decode('ascii')


def hash_checkout(item):
    def hash_str(s):
        hasher = hashlib.sha1()
        hasher.update(s.encode('utf-8'))
        return binascii.hexlify(hasher.digest()).decode('ascii')

    def hash_dict(d):
        item_hashes = []
        for k in sorted(d.keys()):
            assert isinstance(k, str)
            item_hashes.append("{0}={1}".format(k, hash_checkout(d[k])))
        return hash_str(",".join(item_hashes))

    def hash_list(l):
        item_hashes = []
        for item in sorted(l):
            assert isinstance(item, str)
            item_hashes.append(hash_checkout(item))
        return hash_str(",".join(item_hashes))

    if isinstance(item, str) or isinstance(item, bytes):
        return hash_str(item)
    elif isinstance(item, dict):
        return hash_dict(item)
    elif isinstance(item, list):
        return hash_list(item)
    else:
        raise NotImplementedError(str(type(item)))


def get_filename(out_dir, url_str):
    url = urlparse(url_str)
    if url.scheme == 'file':
        path = url_str[len('file://'):]
        return os.path.join(out_dir, os.path.basename(path))
    else:
        return os.path.join(out_dir, os.path.basename(url.path))


def fetch_url(out_filename, url_str):
    url = urlparse(url_str)

    # Handle file:// urls specially since urllib will interpret them to have a
    # netloc when they never have a netloc...
    if url.scheme == 'file':
        abspath = os.path.abspath(url_str[len('file://'):])
        shutil.copyfile(abspath, out_filename)
    else:
        # Download the file.
        with open(out_filename, "w+b") as f:
            with urllib.request.urlopen(url_str) as response:
                shutil.copyfileobj(response, f)


# TODO(cmaloney): Restructure checkout_sources and fetch_sources so all
# the code dealing with one particular kind of source is located
# together rather than half in checkout_sources, half in fetch_sources.
def checkout_sources(sources):
    """Checkout all the sources which are assumed to have been fetched
    already and live in the cache folder."""

    if os.path.exists("src"):
        raise ValidationError(
            "'src' directory already exists, did you have a previous build? " +
            "Currently all builds must be from scratch. Support should be " +
            "added for re-using a src directory when possible. src={}".format(os.path.abspath("src")))
    os.mkdir("src")
    for src, info in sources.items():
        root = os.path.abspath("src/{0}".format(src))
        os.mkdir(root)

        if info['kind'] == 'git':
            bare_folder = os.path.abspath("cache/{0}.git".format(src))

            # Clone into `src/`.
            check_call(["git", "clone", "-q", bare_folder, root])

            # Checkout from the bare repo in the cache folder the specific branch
            # sha1 or tag requested.
            # info["branch"] can be a branch, tag, or commit sha
            check_call(["git", "-C", root, "checkout", "-f", "-q", info["branch"]])

            # TODO(cmaloney): Support patching.
            for patcher in info.get('patches', []):
                raise NotImplementedError()
        elif info['kind'] == 'url':
            cache_filename = get_filename(os.path.abspath("cache"), info['url'])

            # Copy the file(s) into src/
            # TODO(cmaloney): Hardlink to save space?
            filename = get_filename(root, info['url'])
            shutil.copyfile(cache_filename, filename)
        elif info['kind'] == 'url_extract':
            # Extract the files into src.
            cache_filename = get_filename(os.path.abspath("cache"), info['url'])
            check_call(["tar", "-xzf", cache_filename, "--strip-components=1", "-C", root])
        else:
            raise ValidationError("Unsupported source fetch kind: {}".format(info['kind']))


# TODO(cmaloney): Validate sources has all expected fields...
def fetch_sources(sources):
    """Fetch sources to the source cache."""
    ids = dict()
    # TODO(cmaloney): Update if already exists rather than hard-failing
    for src, info in sources.items():

        # Stash directory for download reuse between builds.
        cache_dir = os.path.abspath("cache")
        if not os.path.exists(cache_dir):
            os.mkdir(cache_dir)

        if info['kind'] == 'git':
            # Do a git clone if the cache folder doesn't exist yet, otherwise
            # do a git pull of everything.
            bare_folder = os.path.abspath("cache/{0}.git".format(src))
            if not os.path.exists(bare_folder):
                check_call(["git", "clone", "--bare", "--progress", info['git'], bare_folder])
            else:
                check_call(["git", "-C", bare_folder, "remote", "set-url", "origin", info['git']])
                check_call(["git", "-C", bare_folder, "fetch", "origin", "-t", "+refs/heads/*:refs/heads/*"])

            commit = check_output(["git", "-C", bare_folder, "rev-parse", info["branch"]]).decode('ascii').strip()

            for patcher in info.get('patches', []):
                raise NotImplementedError()

            ids[src] = {
                "commit": commit
            }
        elif info['kind'] == 'url' or info['kind'] == 'url_extract':
            cache_filename = get_filename(os.path.abspath("cache"), info['url'])

            # if the file isn't downloaded yet, get it.
            if not os.path.exists(cache_filename):
                fetch_url(cache_filename, info['url'])

            # TODO(cmaloney): While src can't be reused, the downloaded tarball
            # can so long as it has the same sha1gsum.
            ids[src] = {
                "sha1": sha1(cache_filename)
            }
        else:
            raise ValidationError("Currently only packages from url and git sources are supported")

    return ids


# If work_dir is None, makes a temp folder in the current directory, deletes after.
# NOTE: NOT A LIBRARY FUNCTION. ASSUMES CLI.
def make_bootstrap_tarball(output_name, packages, work_dir=None):
    work_dir_set = work_dir is not None
    if work_dir is None:
        work_dir = tempfile.mkdtemp(prefix='mkpanda_bootstrap_tmp')

    if len(output_name):
        output_name = output_name + '.'
    else:
        # Just for type safety
        output_name = ''

    def make_abs(path):
        return os.path.join(work_dir, path)

    pkgpanda_root = make_abs("opt/mesosphere")
    repository = pkgpanda.Repository(os.path.join(pkgpanda_root, "packages"))

    # Fetch all the packages to the root
    pkg_ids = list()
    for pkg_path in packages:
        # Get the package id from the given package path
        filename = os.path.basename(pkg_path)
        if not filename.endswith(".tar.xz"):
            print("ERROR: Packages must be packaged / end with .tar.xz")
            sys.exit(1)
        pkg_id = filename[:-len(".tar.xz")]
        pkg_ids.append(pkg_id)

        # TODO(camloney): Allow grabbing packages via http.
        def local_fetcher(id, target):
            shutil.unpack_archive(pkg_path, target, "gztar")
        repository.add(local_fetcher, pkg_id)

    # Mark the appropriate roles.
    config_dir = make_abs("etc/mesosphere/roles/")
    if os.path.exists(config_dir):
        shutil.rmtree(config_dir)
    os.makedirs(config_dir)
    for role in roles:
        make_file(os.path.join(config_dir, role))

    # Activate the packages inside the repository.
    # Do generate dcos.target.wants inside the root so that we don't
    # try messing with /etc/systemd/system.
    install = pkgpanda.Install(pkgpanda_root, config_dir, True, False, True, True)
    install.activate(repository, repository.load_packages(pkg_ids))

    # Remove dcos.target.wants from the install since it won't be used
    # on final install systems. Machines should run a `pkgpanda setup`
    # to activate / start all the systemd services for that specific
    # machine.
    shutil.rmtree(make_abs("opt/mesosphere/dcos.target.wants"))

    # Mark the tarball as a bootstrap tarball/filesystem so that
    # dcos-setup.service will fire.
    make_file(make_abs("opt/mesosphere/bootstrap"))

    # Write out an active.json for the bootstrap tarball
    write_json("{}active.json".format(output_name), pkg_ids)

    # Rewrite all the symlinks to point to /opt/mesosphere
    rewrite_symlinks(work_dir, work_dir, "/")

    make_tar("{}bootstrap.tar.xz".format(output_name), pkgpanda_root)

    if not work_dir_set:
        shutil.rmtree(work_dir)
