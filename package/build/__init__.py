import binascii
import hashlib
import os.path
import shutil
import urllib.request
from subprocess import check_call, check_output
from urllib.parse import urlparse

from package.exceptions import ValidationError


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

    if isinstance(item, str) or isinstance(item, bytes):
        return hash_str(item)
    elif isinstance(item, dict):
        return hash_dict(item)
    else:
        raise NotImplementedError()


def fetch_url(out_dir, url_str):
    url = urlparse(url_str)

    # Handle file:// urls specially since urllib will interpret them to have a
    # netloc when they never have a netloc...
    if url.scheme == 'file':
        path = url_str[len('file://'):]
        abspath = os.path.abspath(path)
        filename = os.path.join(out_dir, os.path.basename(path))
        shutil.copyfile(abspath, filename)
        return filename
    else:
        filename = os.path.join(out_dir, os.path.basename(url.path))
        # Download the file.
        with open(filename, "w+b") as f:
            with urllib.request.urlopen(url_str) as response:
                shutil.copyfileobj(response, f)

        return filename


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

        if info['kind'] == 'git':
            # TODO(cmaloney): This will go really badly when updating an existing repo...
            check_call(["git", "clone", info['git'], root])

            # info["branch"] can be a branch, tag, or commit sha
            check_call(["git", "-C", root, "checkout", "-f", info["branch"]])

            commit = check_output(["git", "rev-parse", "HEAD"]).decode('ascii').strip()

            for patcher in info.get('patches', []):
                raise NotImplementedError()

            ids[src] = {
                "commit": commit
            }
        elif info['kind'] == 'url':
            # TODO(cmaloney): While src can't be reused, the downloaded tarball
            # can so long as it has the same sha1sum.
            filename = fetch_url(root, info['url'])
            ids[src] = {
                "sha1": sha1(filename)
            }
        elif info['kind'] == 'url_extract':
            # Like url but do a tarball extract afterwards
            # TODO(cmaloney): While src can't be reused, the downloaded tarball
            # can so long as it has the same sha1sum.
            # TODO(cmaloney): Generalize "Stashing the grabbed copy".
            if not os.path.exists("tmp"):
                os.mkdir("tmp")
            filename = fetch_url("tmp", info['url'])
            ids[src] = {
                "sha1": sha1(filename)
            }

            check_call(["tar", "-xzf", filename, "--strip-components=1", "-C", root])

        else:
            raise ValidationError("Currently only packages from url and git sources are supported")

    return ids
