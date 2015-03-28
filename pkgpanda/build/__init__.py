import binascii
import hashlib
import os.path
import shutil
import urllib.request
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


# TODO(cmaloney): Validate sources has all expected fields...
def checkout_source(sources):
    ids = dict()
    # TODO(cmaloney): Update if already exists rather than hard-failing
    if os.path.exists("src"):
        raise ValidationError(
            "'src' directory already exists, did you have a previous build? " +
            "Currently all builds must be from scratch. Support should be " +
            "added for re-using a src directory when possible. src={}".format(os.path.abspath("src")))
    os.mkdir("src")
    for src, info in sources.items():
        root = os.path.abspath("src/{0}".format(src))
        os.mkdir(root)

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

            # Clone into `src/`.
            check_call(["git", "clone", "-q", bare_folder, root])

            # Checkout from the bare repo in the cache folder the specific branch
            # sha1 or tag requested.
            # info["branch"] can be a branch, tag, or commit sha
            check_call(["git", "-C", root, "checkout", "-f", "-q", info["branch"]])

            # TODO(cmaloney): Support patching.
            for patcher in info.get('patches', []):
                raise NotImplementedError()

            commit = check_output(["git", "-C", root, "rev-parse", "HEAD"]).decode('ascii').strip()

            for patcher in info.get('patches', []):
                raise NotImplementedError()

            ids[src] = {
                "commit": commit
            }
        elif info['kind'] == 'url':
            cache_filename = get_filename(os.path.abspath("cache"), info['url'])

            # if the file isn't downloaded yet, get it.
            if not os.path.exists(cache_filename):
                fetch_url(cache_filename, info['url'])

            # TODO(cmaloney): While src can't be reused, the downloaded tarball
            # can so long as it has the same sha1gsum.
            ids[src] = {
                "sha1": sha1(cache_filename)
            }

            # Copy the file(s) into src/
            # TODO(cmaloney): Hardlink to save space?
            filename = get_filename(root, info['url'])
            shutil.copyfile(cache_filename, filename)
        elif info['kind'] == 'url_extract':
            # Like url but do a tarball extract afterwards
            # TODO(cmaloney): While src can't be reused, the downloaded tarball
            # can so long as it has the same sha1sum.
            # TODO(cmaloney): Generalize "Stashing the grabbed copy".
            cache_filename = get_filename(os.path.abspath("cache"), info['url'])
            if not os.path.exists(cache_filename):
                fetch_url(cache_filename, info['url'])

            ids[src] = {
                "sha1": sha1(cache_filename)
            }

            # Extract the files into src.
            check_call(["tar", "-xzf", cache_filename, "--strip-components=1", "-C", root])

        else:
            raise ValidationError("Currently only packages from url and git sources are supported")

    return ids
