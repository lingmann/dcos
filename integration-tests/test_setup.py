from shutil import copytree
from subprocess import check_call, check_output

from pkgpanda.util import expect_fs

from util import run


def tmp_repository(tmpdir, repo_dir="../tests/resources/packages"):
    repo_path = tmpdir.join("repository")
    copytree(repo_dir, str(repo_path))
    return repo_path


def test_setup(tmpdir):
    repo_path = tmp_repository(tmpdir)
    tmpdir.join("root", "bootstrap").write("", ensure=True)

    check_call(["pkgpanda",
                "setup",
                "--root={0}/root".format(tmpdir),
                "--rooted-systemd",
                "--repository={}".format(repo_path),
                "--config-dir=resources/etc-active",
                "--no-systemd"
                ])
    # TODO(cmaloney): Validate things got placed correctly.

    expect_fs(
        "{0}/root".format(tmpdir),
        {
            "active": ["env", "mesos", "mesos-config"],
            "bin": [
                "mesos",
                "mesos-dir",
                "mesos-master",
                "mesos-slave"],
            "lib": ["libmesos.so"],
            "etc": ["foobar", "some.json"],
            "dcos.target.wants": [],
            "dcos.target": None,
            "environment": None,
            "environment.export": None
        })

    # Introspection should work right
    active = set(check_output([
        "pkgpanda",
        "active",
        "--root={0}/root".format(tmpdir),
        "--rooted-systemd",
        "--repository={}".format(repo_path),
        "--config-dir=resources/etc-active"
        ]).decode("utf-8").split())

    assert active == set(["env--setup", "mesos--0.22.0", "mesos-config--ffddcfb53168d42f92e4771c6f8a8a9a818fd6b8"])
    tmpdir.join("root", "bootstrap").write("", ensure=True)
    # If we setup the same directory again we should get .old files.
    check_call(["pkgpanda",
                "setup",
                "--root={0}/root".format(tmpdir),
                "--rooted-systemd",
                "--repository={}".format(repo_path),
                "--config-dir=resources/etc-active",
                "--no-systemd"
                ])
    # TODO(cmaloney): Validate things got placed correctly.

    expect_fs(
        "{0}/root".format(tmpdir),
        {
            "active": ["env", "mesos", "mesos-config"],
            "bin": [
                "mesos",
                "mesos-dir",
                "mesos-master",
                "mesos-slave"],
            "lib": ["libmesos.so"],
            "etc": ["foobar", "some.json"],
            "dcos.target": None,
            "dcos.target.wants": [],
            "environment": None,
            "environment.export": None,
            "active.old": ["env", "mesos", "mesos-config"],
            "bin.old": [
                "mesos",
                "mesos-dir",
                "mesos-master",
                "mesos-slave"],
            "lib.old": ["libmesos.so"],
            "etc.old": ["foobar", "some.json"],
            "dcos.target.wants.old": [],
            "environment.old": None,
            "environment.export.old": None
        })

    # Should only pickup the packages once / one active set.
    active = set(check_output([
        "pkgpanda",
        "active",
        "--root={0}/root".format(tmpdir),
        "--rooted-systemd",
        "--repository={}".format(repo_path),
        "--config-dir=resources/etc-active"
        ]).decode('utf-8').split())
    assert active == set(["env--setup", "mesos--0.22.0", "mesos-config--ffddcfb53168d42f92e4771c6f8a8a9a818fd6b8"])


def test_activate(tmpdir):
    repo_path = tmp_repository(tmpdir)
    tmpdir.join("root", "bootstrap").write("", ensure=True)
    # TODO(cmaloney): Depending on setup here is less than ideal, but meh.
    check_call(["pkgpanda",
                "setup",
                "--root={0}/root".format(tmpdir),
                "--rooted-systemd",
                "--repository={}".format(repo_path),
                "--config-dir=resources/etc-active",
                "--no-systemd"
                ])

    assert run(["pkgpanda",
                "activate",
                "mesos--0.22.0",
                "mesos-config--ffddcfb53168d42f92e4771c6f8a8a9a818fd6b8",
                "--root={0}/root".format(tmpdir),
                "--rooted-systemd",
                "--repository={}".format(repo_path),
                "--config-dir=resources/etc-active",
                "--no-systemd"]) == ""

    # Check introspection to active is working right.
    active = set(check_output([
        "pkgpanda",
        "active",
        "--root={0}/root".format(tmpdir),
        "--rooted-systemd",
        "--repository={}".format(repo_path),
        "--config-dir=resources/etc-active"
        ]).decode('utf-8').split())
    assert active == set(["mesos--0.22.0", "mesos-config--ffddcfb53168d42f92e4771c6f8a8a9a818fd6b8"])

    assert run(["pkgpanda",
                "activate",
                "mesos--0.22.0",
                "--root={0}/root".format(tmpdir),
                "--rooted-systemd",
                "--repository={}".format(repo_path),
                "--config-dir=resources/etc-active",
                "--no-systemd"]) == ""

    # Check introspection to active is workign right.
    active = set(check_output([
        "pkgpanda",
        "active",
        "--root={0}/root".format(tmpdir),
        "--rooted-systemd",
        "--repository={}".format(repo_path),
        "--config-dir=resources/etc-active"
        ]).decode('utf-8').split())

    assert active == set(["mesos--0.22.0"])

    # TODO(cmaloney): expect_fs


# TODO(cmaloney): Test a full OS setup using http://0pointer.de/blog/projects/changing-roots.html
