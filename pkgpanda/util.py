import json
import os
from shutil import which


def load_json(filename):
    try:
        with open(filename) as f:
            return json.load(f)
    except ValueError as ex:
        raise ValueError("Invalid JSON in {0}: {1}".format(filename, ex)) from ex


def write_json(filename, data):
    with open(filename, "w+") as f:
        return json.dump(data, f)


def load_string(filename):
    with open(filename) as f:
        return f.read()


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
