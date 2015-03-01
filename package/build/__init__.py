import os.path
from subprocess import check_call, check_output

from package.exceptions import ValidationError


# TODO(cmaloney): Validate sources has all expected fields...
def checkout_source(sources):
    ids = dict()
    # TODO(cmaloney): Update if already exists rather than hard-failing
    if os.path.exists("src"):
        raise ValidationError(
            "'src' directory already exists, did you have a previous build? " +
            "Currently all builds must be from scratch. Support should be " +
            "added for re-using a src directory when possible.")
    os.mkdir("src")
    for src, info in sources.items():
        root = os.path.abspath("src/{0}".format(src))
        os.mkdir(root)

        # Fetch the source
        if info['kind'] != 'git':
            raise ValidationError("Currently only packages from git are supported")

        # TODO(cmaloney): This will go really badly when updating an existing repo...
        check_call(["git", "clone", info['git'], "--branch", info["branch"], root])

        commit = check_output(["git", "rev-parse", "HEAD"]).decode('ascii').strip()

        for patcher in info.get('patches', []):
            raise NotImplementedError()

        ids[src] = {
            "commit": commit
        }

    return ids
