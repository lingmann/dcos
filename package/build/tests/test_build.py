import os.path
from shutil import copytree
from subprocess import check_call


def package(resource_dir, tmpdir):
    copytree(resource_dir, os.path.join(str(tmpdir), "workspace"))
    with tmpdir.join("workspace").as_cwd():
        check_call(["mkpanda"])


def test_build(tmpdir):
    package("resources/base", tmpdir)
    # TODO(cmaloney): Check the package exists with the right contents.


def test_single_source(tmpdir):
    package("resources/single_source", tmpdir)
