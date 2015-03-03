import os.path
import shutil
import urllib.request
from subprocess import check_call, check_output
from urllib.parse import urlparse

from package.exceptions import ValidationError


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
            check_call(["git", "clone", info['git'], "--branch", info["branch"], root])

            commit = check_output(["git", "rev-parse", "HEAD"]).decode('ascii').strip()

            for patcher in info.get('patches', []):
                raise NotImplementedError()

            ids[src] = {
                "commit": commit
            }
        elif info['kind'] == 'url':
            url = urlparse(info['url'])
            filename = os.path.join(root, os.path.basename(url.path))
            # Download the file.
            with open(filename, "w+b") as f:
                with urllib.request.urlopen(info['url']) as response:
                    shutil.copyfileobj(response, f)

            ids[src] = {
                "sha1": check_output(["sha1sum", filename]).split()[0].decode('ascii')
            }
        else:
            raise ValidationError("Currently only packages from url and git sources are supported")

    return ids
