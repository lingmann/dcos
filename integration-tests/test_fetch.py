import os

from util import run, expect_fs

fetch_output = """\rFetching: mesos-0.22.0\rFetched: mesos-0.22.0\n"""


def test_fetch(tmpdir):
    # NOTE: tmpdir is explicitly empty because we want to be sure a fetch.
    # succeeds when there isn't anything yet.
    # Start a simpleHTTPServer to serve the packages
    # fetch a couple packages
    assert run([
            "pkgpanda",
            "fetch",
            "mesos-0.22.0",
            "--repository={0}".format(tmpdir),
            "--repository-url=file://{0}/../tests/resources/remote_repo/".format(os.getcwd())
        ]) == fetch_output

    # Ensure that the package at least somewhat extracted correctly.
    expect_fs(
        "{0}".format(tmpdir),
        {
            "mesos-0.22.0": ["lib", "bin_master", "bin_slave", "pkginfo.json", "bin"]
        })
    # TODO(cmaloney): Test multiple fetches on one line.
    # TODO(cmaloney): Test unable to fetch case.
