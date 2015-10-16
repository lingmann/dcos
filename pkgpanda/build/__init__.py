import binascii
import hashlib
import os.path
import shutil
import urllib.request
from subprocess import CalledProcessError, check_call, check_output
from urllib.parse import urlparse

from pkgpanda.exceptions import ValidationError
from pkgpanda.util import load_string


def sha1(filename):
    return check_output(["sha1sum", filename]).split()[0].decode('ascii')


def hash_checkout(item):
    def hash_str(s):
        hasher = hashlib.sha1()
        hasher.update(s.encode('utf-8'))
        return binascii.hexlify(hasher.digest()).decode('ascii')

    def hash_int(i):
        return hash_str(str(i))

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
    elif isinstance(item, int):
        return hash_int(item)
    else:
        raise NotImplementedError("{} of type {}".format(item, type(item)))


def get_filename(out_dir, url_str):
    url = urlparse(url_str)
    if url.scheme == 'file':
        path = url_str[len('file://'):]
        return os.path.join(out_dir, os.path.basename(path))
    else:
        return os.path.join(out_dir, os.path.basename(url.path))


def _identify_archive_type(filename):
    """Identify archive type basing on extension

    Args:
        filename: the path to the archive

    Returns:
        Currently only zip and tar.*/tgz archives are supported. The return values
        for them are 'tar' and 'zip' respectively
    """
    parts = filename.split('.')
    if len(parts) >= 3 and parts[-2] == 'tar' or len(parts) >= 2 and parts[-1] == 'tgz':
        return 'tar'
    elif len(parts) >= 2 and parts[-1] == 'zip':
        return 'zip'
    else:
        return 'unknown'


def _check_components_sanity(path):
    """Check if archive is sane

    Check if there is only one top level component (directory) in the extracted
    archive's directory.

    Args:
        path: path to the extracted archive's directory

    Raises:
        Raise an exception if there is anything else than a single directory
    """
    dir_contents = os.listdir(path)

    if len(dir_contents) != 1 or not os.path.isdir(os.path.join(path, dir_contents[0])):
        raise ValidationError("Extracted archive has more than one top level"
                              "component, unable to strip it.")


def _strip_components_paths(path, components=0):
    """Simulate tar's --strip-components behaviour using file operations

    Unarchivers like unzip do not support stripping component paths while
    inflating the archive. This function simulates this behaviour by moving
    files around and then removing the TLD directory.

    Args:
        path: path where extracted archive contents can be found
        components: compontents to strip
    """
    if components <= 0:
        return

    _check_components_sanity(path)

    top_level_dir = os.path.join(path, os.listdir(path)[0])

    contents = os.listdir(top_level_dir)

    for entry in contents:
        old_path = os.path.join(top_level_dir, entry)
        new_path = os.path.join(path, entry)
        os.rename(old_path, new_path)

    os.rmdir(top_level_dir)


def extract_archive(archive, dst_dir):
    archive_type = _identify_archive_type(archive)

    if archive_type == 'tar':
        check_call(["tar", "-xf", archive, "--strip-components=1", "-C", dst_dir])
    elif archive_type == 'zip':
        check_call(["unzip", "-x", archive, "-d", dst_dir])
        # unzip binary does not support '--strip-components=1',
        _strip_components_paths(dst_dir, components=1)
    else:
        raise ValidationError("Unsupported archive: {}".format(os.path.basename(archive)))


def fetch_url(out_filename, url_str):
    url = urlparse(url_str)

    # Handle file:// urls specially since urllib will interpret them to have a
    # netloc when they never have a netloc...
    try:
        if url.scheme == 'file':
            abspath = os.path.abspath(url_str[len('file://'):])
            shutil.copyfile(abspath, out_filename)
        else:
            # Download the file.
            with open(out_filename, "w+b") as f:
                with urllib.request.urlopen(url_str) as response:
                    shutil.copyfileobj(response, f)
    except Exception as fetch_exception:
        print("ERROR: Unable to fetch {}".format(url_str), fetch_exception)
        try:
            os.remove(out_filename)
        except Exception as cleanup_exception:
            print("ERROR: Unable to remove temp file: {}. Future builds may have problems because of it.".format(
                out_filename), cleanup_exception)
        raise


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
            ref = info.get('ref', None)
            if ref is None:
                ref = info['branch']

            check_call([
                "git",
                "--git-dir",
                root + "/.git",
                "--work-tree",
                root, "checkout",
                "-f",
                "-q",
                ref])

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
            extract_archive(cache_filename, root)
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
                check_call([
                    "git",
                    "--git-dir",
                    bare_folder,
                    "remote",
                    "set-url",
                    "origin",
                    info['git']])
                check_call([
                    "git",
                    "--git-dir",
                    bare_folder,
                    "fetch",
                    "origin",
                    "-t",
                    "+refs/heads/*:refs/heads/*"])

            if 'branch' in info:
                raise ValidationError("Use of 'branch' field has been removed. Please replace with 'ref'")

            if 'ref' not in info:
                raise ValidationError("Must specify ref inside fo the buildinfo")

            ref = info['ref']

            def get_sha1(git_ref):
                try:
                    return check_output([
                        "git",
                        "--git-dir",
                        bare_folder,
                        "rev-parse",
                        git_ref + "^{commit}"]).decode('ascii').strip()
                except CalledProcessError as ex:
                    raise ValidationError(
                        "ERROR: Unable to find ref '{}' in source '{}': {}".format(git_ref, src, ex)) from ex

            commit = get_sha1(ref)

            # Warn if the ref_origin is set and gives a different sha1 than the
            # current ref.
            if 'ref_origin' in info:
                origin_commit = None
                try:
                    origin_commit = get_sha1(info['ref_origin'])
                except Exception as ex:
                    print("WARNING: Unable to find sha1 of ref_origin:", ex)
                if origin_commit != commit:
                    print("WARNING: Current ref doesn't match the ref origin. "
                          "Package ref should probably be updated to pick up "
                          "new changes to the code:" +
                          " Current: {}, Origin: {}".format(commit,
                                                            origin_commit))

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


def get_last_bootstrap_set(path):
    assert path[-1] != '/'
    last_bootstrap = {}

    # Get all the tree variants. If there is a treeinfo.json for the default
    # variant this won't catch it because that would be just 'treeinfo.json' /
    # not have the '.' before treeinfo.json.
    for filename in os.listdir(path):
        if filename.endswith('.treeinfo.json'):
            variant_name = filename[:-len('.treeinfo.json')]
            bootstrap_id = load_string(path + '/' + variant_name + '.bootstrap.latest')
            last_bootstrap[variant_name] = bootstrap_id

    # Add in None / the default variant with a python None.
    # Use a python none so that handling it incorrectly around strings will
    # result in more visible errors than empty string would.
    last_bootstrap[None] = load_string(path + '/' + 'bootstrap.latest')

    return last_bootstrap
