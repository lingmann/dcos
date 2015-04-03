""" Test reading and changing the active set of available packages"""

import shutil

from pkgpanda import Install, Repository
from pkgpanda.util import expect_fs

import pytest


@pytest.fixture
def repository():
    return Repository("resources/packages")


@pytest.fixture
def install():
    return Install("resources/install", "resources/systemd", True, False, True)


# Test that the active set is detected correctly.
def test_active(install):
    active = install.get_active()
    assert type(active) is set

    assert active == set(['mesos-config--ffddcfb53168d42f92e4771c6f8a8a9a818fd6b8', 'mesos--0.22.0'])

    # TODO(cmaloney): More comprehensive testing of the validation checks

# TODO(cmaloney): All packages must be locally available in the repository


# TODO(cmaloney): No previous state, first active

# TODO(cmaloney): Updating active which is already full

# TODO(cmaloney): Activate failed, loading old/new

def test_recovery_noop(install):
    # No action if nothing to do
    action, _ = install.recover_swap_active()
    assert not action


def test_recovery_archive(tmpdir, repository):
    # Recover from the "archive" state correctly.
    shutil.copytree("resources/install_recovery_archive", str(tmpdir.join("install")), symlinks=True)
    install = Install(str(tmpdir.join("install")), "resources/systemd", True, False, True)
    action, _ = install.recover_swap_active()
    assert action

    # TODO(cmaloney): expect_fs
    expect_fs(
        str(tmpdir.join("install")),
        {
            "active": ["mesos"],
            "active.old": ["mesos"],
            "bin": ["mesos", "mesos-dir"],
            "dcos.target.wants": [".gitignore"],
            "environment": None,
            "environment.export": None,
            "environment.old": None,
            "etc": [".gitignore"],
            "lib": ["libmesos.so"]
        })


def test_recovery_move_new(tmpdir, repository):
    # From the "move_new" state correctly.
    shutil.copytree("resources/install_recovery_move", str(tmpdir.join("install")), symlinks=True)
    install = Install(str(tmpdir.join("install")), "resources/systemd", True, False, True)
    action, _ = install.recover_swap_active()
    assert action

    # TODO(cmaloney): expect_fs
    expect_fs(
        str(tmpdir.join("install")),
        {
            "active": ["mesos"],
            "bin": ["mesos", "mesos-dir"],
            "dcos.target.wants": [".gitignore"],
            "environment": None,
            "environment.export": None,
            "etc": [".gitignore"],
            "lib": ["libmesos.so"]
        })
