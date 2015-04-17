import json
import os
from itertools import chain
from shutil import rmtree, which
from subprocess import check_call


def extract_tarball(path, target):
    """Extract the tarball into target.

    If there are any errors, delete the folder being extracted to.
    """
    # TODO(cmaloney): Validate extraction will pass before unpacking as much as possible.
    # TODO(cmaloney): Unpack into a temporary directory then move into place to
    # prevent partial extraction from ever laying around on the filesystem.
    try:
        assert os.path.exists(path)
        check_call(['mkdir', '-p', target])
        check_call(['tar', '-xf', path, '-C', target])
    except:
        # If there are errors, we can't really cope since we are already in an error state.
        rmtree(target, ignore_errors=True)
        raise


def load_json(filename):
    try:
        with open(filename) as f:
            return json.load(f)
    except ValueError as ex:
        raise ValueError("Invalid JSON in {0}: {1}".format(filename, ex)) from ex


def make_file(name):
    with open(name, 'a'):
        pass


def write_json(filename, data):
    with open(filename, "w+") as f:
        return json.dump(data, f)


def write_string(filename, data):
    with open(filename, "w+") as f:
        return f.write(data)


def load_string(filename):
    with open(filename) as f:
        return f.read().strip()


def if_exists(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except FileNotFoundError:
        return None


def expect_folder(path, files):
    path_contents = os.listdir(path)
    assert set(path_contents) == set(files)


def expect_fs(folder, contents):
    if isinstance(contents, list):
        expect_folder(folder, contents)
    elif isinstance(contents, dict):
        expect_folder(folder, contents.keys())

        for path in iter(contents):
            if contents[path] is not None:
                expect_fs(os.path.join(folder, path), contents[path])
    else:
        raise ValueError("Invalid type {0} passed to expect_fs".format(type(contents)))


def make_tar(result_filename, change_folder):
    tar_cmd = ["tar", "--numeric-owner", "--owner=0", "--group=0"]
    if which("pxz"):
        tar_cmd += ["--use-compress-program=pxz", "-cf"]
    else:
        tar_cmd += ["-cJf"]
    tar_cmd += [result_filename, "-C", change_folder, "."]
    check_call(tar_cmd)


def rewrite_symlinks(root, old_prefix, new_prefix):
    # Find the symlinks and rewrite them from old_prefix to new_prefix
    # All symlinks not beginning with old_prefix are ignored because
    # packages may contain arbitrary symlinks.
    for root_dir, dirs, files in os.walk(root):
        for name in chain(files, dirs):
            full_path = os.path.join(root_dir, name)
            if os.path.islink(full_path):
                # Rewrite old_prefix to new_prefix if present.
                target = os.readlink(full_path)
                if target.startswith(old_prefix):
                    new_target = os.path.join(new_prefix, target[len(old_prefix)+1:].lstrip('/'))
                    # Remove the old link and write a new one.
                    os.remove(full_path)
                    os.symlink(new_target, full_path)
