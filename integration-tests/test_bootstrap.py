from subprocess import check_call, check_output

from package.util import expect_fs

from util import run


def test_bootstrap(tmpdir):
    check_call(["pkgpanda",
                "setup",
                "--root={0}/root".format(tmpdir),
                "--repository=../tests/resources/packages",
                "--config-dir=resources/etc-active",
                "--no-systemd"
                ])
    # TODO(cmaloney): Validate things got placed correctly.

    expect_fs(
        "{0}/root".format(tmpdir),
        {
            "active": ["mesos", "mesos-config"],
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

    # Introspection should work right
    active = set(check_output([
        "pkgpanda",
        "active",
        "--root={0}/root".format(tmpdir),
        "--repository=../tests/resources/packages",
        "--config-dir=resources/etc-active"
        ]).decode("utf-8").split())

    assert active == set(["mesos--0.22.0", "mesos-config--ffddcfb53168d42f92e4771c6f8a8a9a818fd6b8"])

    # If we bootstarp the same directory again we should get .old files.
    check_call(["pkgpanda",
                "setup",
                "--root={0}/root".format(tmpdir),
                "--repository=../tests/resources/packages",
                "--config-dir=resources/etc-active",
                "--no-systemd"
                ])
    # TODO(cmaloney): Validate things got placed correctly.

    expect_fs(
        "{0}/root".format(tmpdir),
        {
            "active": ["mesos", "mesos-config"],
            "bin": [
                "mesos",
                "mesos-dir",
                "mesos-master",
                "mesos-slave"],
            "lib": ["libmesos.so"],
            "etc": ["foobar"],
            "dcos.target.wants": [],
            "environment": None,
            "active.old": ["mesos", "mesos-config"],
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

    # Should only pickup the packages once / one active set.
    active = set(check_output([
        "pkgpanda",
        "active",
        "--root={0}/root".format(tmpdir),
        "--repository=../tests/resources/packages",
        "--config-dir=resources/etc-active"
        ]).decode('utf-8').split())
    assert active == set(["mesos--0.22.0", "mesos-config--ffddcfb53168d42f92e4771c6f8a8a9a818fd6b8"])


def test_activate(tmpdir):
    # TODO(cmaloney): Depending on bootstrap here is less than ideal, but meh.
    check_call(["pkgpanda",
                "setup",
                "--root={0}/root".format(tmpdir),
                "--repository=../tests/resources/packages",
                "--config-dir=resources/etc-active",
                "--no-systemd"
                ])

    assert run(["pkgpanda",
                "activate",
                "mesos--0.22.0",
                "mesos-config--ffddcfb53168d42f92e4771c6f8a8a9a818fd6b8",
                "--root={0}/root".format(tmpdir),
                "--repository=../tests/resources/packages",
                "--config-dir=resources/etc-active",
                "--no-systemd"]) == ""

    # Check introspection to active is working right.
    active = set(check_output([
        "pkgpanda",
        "active",
        "--root={0}/root".format(tmpdir),
        "--repository=../tests/resources/packages",
        "--config-dir=resources/etc-active"
        ]).decode('utf-8').split())
    assert active == set(["mesos--0.22.0", "mesos-config--ffddcfb53168d42f92e4771c6f8a8a9a818fd6b8"])

    assert run(["pkgpanda",
                "activate",
                "mesos--0.22.0",
                "--root={0}/root".format(tmpdir),
                "--repository=../tests/resources/packages",
                "--config-dir=resources/etc-active",
                "--no-systemd"]) == ""

    # Check introspection to active is workign right.
    active = set(check_output([
        "pkgpanda",
        "active",
        "--root={0}/root".format(tmpdir),
        "--repository=../tests/resources/packages",
        "--config-dir=resources/etc-active"
        ]).decode('utf-8').split())

    assert active == set(["mesos--0.22.0"])

    # TODO(cmaloney): expect_fs


# TODO(cmaloney): Test a full OS setup using http://0pointer.de/blog/projects/changing-roots.html
