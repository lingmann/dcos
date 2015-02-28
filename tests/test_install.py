""" Test reading and changing the active set of available packages"""

from package import Install, Repository

import pytest


@pytest.fixture
def repository():
    return Repository("resources/packages")


@pytest.fixture
def install():
    return Install("resources/install", "resources/systemd")


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
