import os
from subprocess import check_call

from util import run


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


def test_bootstrap(tmpdir):
    check_call(["pkgpanda",
                "bootstrap",
                "--root={0}/root".format(tmpdir),
                "--repository=../tests/resources/packages",
                "--config-dir=resources/etc-active"
                ])
    # TODO(cmaloney): Validate things got placed correctly.

    expect_fs(
        "{0}/root".format(tmpdir),
        {
            "bin": [
                "mesos",
                "mesos-dir",
                "mesos-master",
                "mesos-slave"],
            "lib": ["libmesos.so"],
            "etc": ["foobar"],
            "dcos.target.wants": [],
            "environment": None
        })

    # If we bootstarp the same directory again we should get .old files.
    check_call(["pkgpanda",
                "bootstrap",
                "--root={0}/root".format(tmpdir),
                "--repository=../tests/resources/packages",
                "--config-dir=resources/etc-active"
                ])
    # TODO(cmaloney): Validate things got placed correctly.

    expect_fs(
        "{0}/root".format(tmpdir),
        {
            "bin": [
                "mesos",
                "mesos-dir",
                "mesos-master",
                "mesos-slave"],
            "lib": ["libmesos.so"],
            "etc": ["foobar"],
            "dcos.target.wants": [],
            "environment": None,
            "bin.old": [
                "mesos",
                "mesos-dir",
                "mesos-master",
                "mesos-slave"],
            "lib.old": ["libmesos.so"],
            "etc.old": ["foobar"],
            "dcos.target.wants.old": [],
            "environment.old": None
        })


def test_activate(tmpdir):
    # TODO(cmaloney): Depending on bootstrap here is less than ideal, but meh.
    check_call(["pkgpanda",
                "bootstrap",
                "--root={0}/root".format(tmpdir),
                "--repository=../tests/resources/packages",
                "--config-dir=resources/etc-active"
                ])

    assert run(["pkgpanda",
                "activate",
                "mesos-0.22.0",
                "mesos-config-ffddcfb53168d42f92e4771c6f8a8a9a818fd6b8",
                "--root={0}/root".format(tmpdir),
                "--repository=../tests/resources/packages",
                "--config-dir=resources/etc-active"]) == ""

    # TODO(cmaloney): expect_fs


# TODO(cmaloney): Test a full OS bootstrap using http://0pointer.de/blog/projects/changing-roots.html
