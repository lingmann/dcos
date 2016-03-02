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


def hash_folder(directory):
    return check_output([
        "/bin/bash",
        "-o", "nounset",
        "-o", "pipefail",
        "-o", "errexit",
        "-c",
        "find {} -type f -print0 | sort -z | xargs -0 sha1sum | sha1sum | cut -d ' ' -f 1".format(
            directory)
        ]).decode('ascii').strip()
    raise


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

    # no extension
    if len(parts) < 2:
        return 'unknown'

    # one extension
    if parts[-1] == 'tgz':
        return 'tar'
    if parts[-1] == 'zip':
        return 'zip'

    # two extensions
    if len(parts) >= 3 and parts[-2] == 'tar':
        return 'tar'

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


def _strip_first_path_component(path):
    """Simulate tar's --strip-components=1 behaviour using file operations

    Unarchivers like unzip do not support stripping component paths while
    inflating the archive. This function simulates this behaviour by moving
    files around and then removing the TLD directory.

    Args:
        path: path where extracted archive contents can be found
    """
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
        _strip_first_path_component(dst_dir)
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

        if info['kind'] == 'git' or info['kind'] == 'git_local':
            bare_folder = os.path.abspath("cache/{0}.git".format(src))

            # Clone into `src/`.
            check_call(["git", "clone", "-q", bare_folder, root])

            # Checkout from the bare repo in the cache folder at the specific sha1
            ref = info['ref']
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


# Ref must be a git sha-1. We then pass it through get_sha1 to make
# sure it is a sha-1 for the commit, not the tree, tag, or any other
# git object.
def is_sha(sha_str):
    try:
        return int(sha_str, 16) and len(sha_str) == 40
    except ValueError:
        return False


def fetch_git(src, git_uri):
    # Do a git clone if the cache folder doesn't exist yet, otherwise
    # do a git pull of everything.
    bare_folder = os.path.abspath("cache/{0}.git".format(src))
    if not os.path.exists(bare_folder):
        check_call(["git", "clone", "--bare", "--progress", git_uri, bare_folder])
    else:
        check_call([
            "git",
            "--git-dir",
            bare_folder,
            "remote",
            "set-url",
            "origin",
            git_uri])
        check_call([
            "git",
            "--git-dir",
            bare_folder,
            "fetch",
            "origin",
            "-t",
            "+refs/heads/*:refs/heads/*"])

    return bare_folder


# TODO(cmaloney): Validate sources has all expected fields...
def fetch_sources(sources):
    """Fetch sources to the source cache."""
    ids = dict()

    def get_git_sha1(git_dir, git_ref, bare):
        try:
            return check_output(
                ["git"] +
                (["--git-dir", git_dir] if bare else ['-C', git_dir]) +
                ["rev-parse", git_ref + "^{commit}"]
                ).decode('ascii').strip()
        except CalledProcessError as ex:
            raise ValidationError(
                "Unable to find ref '{}' in source '{}': {}".format(git_ref, src, ex)) from ex

    # TODO(cmaloney): Update if already exists rather than hard-failing
    for src, info in sorted(sources.items()):

        # Stash directory for download reuse between builds.
        cache_dir = os.path.abspath("cache")
        if not os.path.exists(cache_dir):
            os.mkdir(cache_dir)

        if info['kind'] == 'git':
            bare_folder = fetch_git(src, info['git'])

            if 'branch' in info:
                raise ValidationError("Use of 'branch' field has been removed. Please replace with 'ref'")

            if 'ref' not in info:
                raise ValidationError("Must specify ref inside fo the buildinfo")

            ref = info['ref']

            if not is_sha(ref):
                raise ValidationError("ref must be a git commit sha-1 (40 character hex string). Got: " + ref)
            commit = get_git_sha1(bare_folder, ref, True)

            # Warn if the ref_origin is set and gives a different sha1 than the
            # current ref.
            if 'ref_origin' in info:
                origin_commit = None
                try:
                    origin_commit = get_git_sha1(bare_folder, info['ref_origin'], True)
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
        elif info['kind'] == 'git_local':
            if info.keys() > {'kind', 'rel_path'}:
                raise ValidationError("Only kind, rel_path can be specified for git_local")
            if os.path.isabs(info['rel_path']):
                raise ValidationError("rel_path must be a relative path to the current directory "
                                      "when used with git_local. Using a relative path means others "
                                      "that clone the repository will have things just work rather "
                                      "than a path.")
            src_repo_path = os.path.abspath(info['rel_path']).rstrip('/')

            # Make sure there are no local changes, we can't `git clone` local changes.
            try:
                git_status = check_output([
                    'git',
                    '-C',
                    src_repo_path,
                    'status',
                    '--porcelain',
                    '-uno',
                    '-z']).decode()
                if len(git_status):
                    raise ValidationError("No local changse are allowed in the git_local_work base repository. "
                                          "Use `git -C {0} status` to see local changes. "
                                          "All local changes must be committed or stashed before the "
                                          "package can be built. One workflow (temporary commit): `git -C {0} "
                                          "commit -am TMP` to commit everything, build the package, "
                                          "`git -C {0} reset --soft HEAD^` to get back to where you were.".format(
                                                src_repo_path))
            except CalledProcessError as ex:
                raise ValidationError("Unable to check status of git_local_work checkout {}. Is the "
                                      "rel_path correct?".format(info['rel_path']))

            # Set the ref
            commit = get_git_sha1(src_repo_path, "HEAD", False)

            # TODO(cmaloney): HACK. We set the ref here, so it gets picked up by checkout_sources.
            info['ref'] = commit

            ids[src] = {
                "commit": commit
            }

            # Clone to the bare folder so checkout_sources will work
            fetch_git(src, src_repo_path)

        elif info['kind'] == 'url' or info['kind'] == 'url_extract':
            cache_filename = get_filename(os.path.abspath("cache"), info['url'])

            # if the file isn't downloaded yet, get it.
            if not os.path.exists(cache_filename):
                fetch_url(cache_filename, info['url'])

            # Validate the sha1 of the source is given and matches the sha1
            file_sha = sha1(cache_filename)
            if 'sha1' not in info:
                raise ValidationError(
                    "url and url_extract both require a sha1 to be given in the buildinfo but no sha1 " +
                    "found for file " + info['url'] + " which when downloaded has the sha1 " + file_sha)

            if info['sha1'] != file_sha:
                corrupt_filename = cache_filename + '.corrupt'
                check_call(['mv', cache_filename, corrupt_filename])
                raise ValidationError(
                    "Provided sha1 didn't match sha1 of downloaded file, corrupt download saved as {}. "
                    "Provided: {}, Download file's sha1: {}, Url: {}".format(
                        corrupt_filename, info['sha1'], file_sha, info['url']))
            ids[src] = {
                "downloaded_sha1": file_sha
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
