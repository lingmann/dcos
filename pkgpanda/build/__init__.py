import abc
import binascii
import hashlib
import os.path
import shutil
from subprocess import CalledProcessError, check_call, check_output

from pkgpanda.exceptions import ValidationError
from pkgpanda.util import download, load_string


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


class SourceFetcher(metaclass=abc.ABCMeta):

    def __init__(self, name, src_info, package_dir):
        self.name = name
        self.package_dir = package_dir
        self.kind = src_info['kind']

    @abc.abstractmethod
    def get_id(self):
        """Returns a unique id for the particular version of the particular source (sha1 of tarball, git commit, etc)"""
        pass

    @abc.abstractmethod
    def checkout_to(self, directory):
        """Makes the artifact appear in the passed directory"""
        pass


def get_git_sha1(bare_folder, ref):
        try:
            return check_output([
                "git",
                "--git-dir", bare_folder,
                "rev-parse", ref + "^{commit}"
                ]).decode('ascii').strip()
        except CalledProcessError as ex:
            raise ValidationError(
                "Unable to find ref '{}' in '{}': {}".format(ref, bare_folder, ex)) from ex


class GitSrcFetcher(SourceFetcher):
    def __init__(self, name, src_info, package_dir):
        super().__init__(name, src_info, package_dir)

        assert self.kind == 'git'

        self.bare_folder = package_dir + "/cache/{}.git".format(name)

        if src_info.keys() < {'git', 'ref'}:
            raise ValidationError(
                "git source must have keys 'git' (the repo to fetch) and 'ref' (the sha-1 to checkout)")
        if src_info.keys() > {'git', 'kind', 'ref', 'ref_origin'}:
            raise ValidationError("git source can only have 'git', 'ref', and 'ref_origin'")

        if not is_sha(src_info['ref']):
            raise ValidationError("ref must be a sha1. Got: {}".format(src_info['ref']))

        # TODO(cmaloney): Only make a bare clone to validate the sha-1 is in the git
        # repository and matches the branch when checkout_sources is done.
        fetch_git(self.bare_folder, src_info['git'])
        self.commit = get_git_sha1(self.bare_folder, src_info['ref'])

        # Warn if the ref_origin is set and gives a different sha1 than the
        # current ref.
        if 'ref_origin' in src_info:
            origin_commit = None
            try:
                origin_commit = get_git_sha1(self.bare_folder, src_info['ref_origin'])
            except Exception as ex:
                print("WARNING: Unable to find sha1 of ref_origin:", ex)
            if origin_commit != self.commit:
                print("WARNING: Current ref doesn't match the ref origin. "
                      "Package ref should probably be updated to pick up "
                      "new changes to the code:" +
                      " Current: {}, Origin: {}".format(self.commit,
                                                        origin_commit))

    def get_id(self):
        return {"commit": self.commit}

    def checkout_to(self, directory):
        # Clone into `src/`.
        check_call(["git", "clone", "-q", self.bare_folder, directory])

        # Checkout from the bare repo in the cache folder at the specific sha1
        check_call([
            "git",
            "--git-dir",
            directory + "/.git",
            "--work-tree",
            directory, "checkout",
            "-f",
            "-q",
            self.commit])


class GitLocalSrcFetcher(SourceFetcher):
    def __init__(self, name, src_info, package_dir):
        super().__init__(name, src_info, package_dir)

        assert self.kind == 'git_local'

        if src_info.keys() > {'kind', 'rel_path'}:
            raise ValidationError("Only kind, rel_path can be specified for git_local")
        if os.path.isabs(src_info['rel_path']):
            raise ValidationError("rel_path must be a relative path to the current directory "
                                  "when used with git_local. Using a relative path means others "
                                  "that clone the repository will have things just work rather "
                                  "than a path.")
        self.src_repo_path = os.path.normpath(package_dir + '/' + src_info['rel_path']).rstrip('/')

        # Make sure there are no local changes, we can't `git clone` local changes.
        try:
            git_status = check_output([
                'git',
                '-C',
                self.src_repo_path,
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
                                      "`git -C {0} reset --soft HEAD^` to get back to where you were.\n\n"
                                      "Found changes: {1}".format(
                                            self.src_repo_path,
                                            git_status))
        except CalledProcessError:
            raise ValidationError("Unable to check status of git_local_work checkout {}. Is the "
                                  "rel_path correct?".format(src_info['rel_path']))

        self.commit = get_git_sha1(self.src_repo_path + "/.git", "HEAD")

    def get_id(self):
        return {"commit": self.commit}

    def checkout_to(self, directory):
        # Clone into `src/`.
        check_call(["git", "clone", "-q", self.src_repo_path, directory])

        # Make sure we got the right commit as head
        assert get_git_sha1(directory + "/.git", "HEAD") == self.commit

        # Checkout from the bare repo in the cache folder at the specific sha1
        check_call([
            "git",
            "--git-dir",
            directory + "/.git",
            "--work-tree",
            directory, "checkout",
            "-f",
            "-q",
            self.commit])


class UrlSrcFetcher(SourceFetcher):
    def __init__(self, name, src_info, package_dir):
        super().__init__(name, src_info, package_dir)

        assert self.kind in {'url', 'url_extract'}

        if src_info.keys() != {'kind', 'sha1', 'url'}:
                raise ValidationError(
                        "url and url_extract sources must have exactly 'sha1' (sha1 of the artifact"
                        " which will be downloaded), and 'url' (url to download artifact) as options")

        self.url = src_info['url']
        self.extract = (self.kind == 'url_extract')
        self.cache_filename = self._get_filename(package_dir + "/cache")

        # TODO(cmaloney): Delay downloading until checkout_to
        # if the file isn't downloaded yet, get it.
        if not os.path.exists(self.cache_filename):
            download(self.cache_filename, self.url, package_dir)

        self.sha = src_info['sha1']

        # Validate the sha1 of the source is given and matches the sha1
        file_sha = sha1(self.cache_filename)

        if src_info['sha1'] != file_sha:
            corrupt_filename = self.cache_filename + '.corrupt'
            check_call(['mv', self.cache_filename, corrupt_filename])
            raise ValidationError(
                "Provided sha1 didn't match sha1 of downloaded file, corrupt download saved as {}. "
                "Provided: {}, Download file's sha1: {}, Url: {}".format(
                    corrupt_filename, src_info['sha1'], file_sha, self.url))

    def _get_filename(self, out_dir):
        assert '://' in self.url, "Scheme separator not found in url {}".format(self.url)
        return os.path.join(out_dir, os.path.basename(self.url.split('://', 2)[1]))

    def get_id(self):
        return {
            "downloaded_sha1": self.sha
        }

    def checkout_to(self, directory):
        if self.extract:
            extract_archive(self.cache_filename, directory)
        else:
            # Copy the file(s) into src/
            # TODO(cmaloney): Hardlink to save space?
            shutil.copyfile(self.cache_filename, self._get_filename(directory))


src_fetchers = {
    "git": GitSrcFetcher,
    "git_local": GitLocalSrcFetcher,
    "url": UrlSrcFetcher,
    "url_extract": UrlSrcFetcher
}


# Ref must be a git sha-1. We then pass it through get_sha1 to make
# sure it is a sha-1 for the commit, not the tree, tag, or any other
# git object.
def is_sha(sha_str):
    try:
        return int(sha_str, 16) and len(sha_str) == 40
    except ValueError:
        return False


def fetch_git(bare_folder, git_uri):
    # Do a git clone if the cache folder doesn't exist yet, otherwise
    # do a git pull of everything.
    if not os.path.exists(bare_folder):
        check_call(["git", "clone", "--mirror", "--progress", git_uri, bare_folder])
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
            "remote",
            "update",
            "origin"])

    return bare_folder


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
