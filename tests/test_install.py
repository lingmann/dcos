from package import Install, Repository, activate

import pytest
""" Test changing the active set of packages """


@pytest.fixture
def repository():
    return Repository("resources/packages")

# All packages must be locally available


# No previous state, first active
def test_new_activate(tmpdir, repository):
    raise NotImplementedError()
    activate(tmpdir, repository)

# Updating active

# Activate failed, loading old/new
