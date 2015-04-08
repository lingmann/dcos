from shutil import copytree
from subprocess import check_call


def package(resource_dir, name, tmpdir):
    pkg_dir = tmpdir.join(name)
    copytree(resource_dir, str(pkg_dir))
    with pkg_dir.as_cwd():
        check_call(["mkpanda"])


def test_build(tmpdir):
    package("resources/base", "b", tmpdir)
    # TODO(cmaloney): Check the package exists with the right contents.


def test_single_source(tmpdir):
    package("resources/single_source", "a", tmpdir)


def test_url_extract(tmpdir):
    package("resources/url_extract", "a", tmpdir)
