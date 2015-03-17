from shutil import copytree

from util import run


list_output = """mesos--0.22.0
mesos-config--ffddcfb53168d42f92e4771c6f8a8a9a818fd6b8
"""

active_output = """mesos--0.22.0
mesos-config--ffddcfb53168d42f92e4771c6f8a8a9a818fd6b8
"""


def test_list():
    assert run(["pkgpanda", "list", "--repository=../tests/resources/packages"]) == list_output


def test_active():
    assert run(["pkgpanda", "active", "--root=../tests/resources/install"]) == active_output


def test_remove(tmpdir):
    repo_dir = str(tmpdir.join("repo"))
    copytree("../tests/resources/packages", repo_dir)
    assert run([
        "pkgpanda",
        "remove",
        "mesos--0.22.0",
        "--repository={}".format(repo_dir),
        "--root=../tests/resources/install_empty"])

    packages = set(run(["pkgpanda", "list", "--repository={}".format(repo_dir)]).split())
    assert packages == set(["mesos-config--ffddcfb53168d42f92e4771c6f8a8a9a818fd6b8"])

    # TODO(cmaloney): Test removing a non-existant package.
    # TODO(cmaloney): Test removing an active package.
