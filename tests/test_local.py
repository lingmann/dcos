import package.exceptions
from package import Repository, valid_active_set

import pytest

"""Test local unpacked packages repository actions"""


@pytest.fixture
def repository():
    return Repository("resources/packages")


def test_list(repository):
    packages = repository.list()
    assert type(packages) is set
    assert packages == set(['mesos-config-ffddcfb53168d42f92e4771c6f8a8a9a818fd6b8', 'mesos-0.22.0', "invalid-package"])


def test_active(repository):
    active = repository.get_active()
    assert type(active) is set

    assert active <= repository.list()

    assert active == set(["mesos-0.22.0", "mesos-config-ffddcfb53168d42f92e4771c6f8a8a9a818fd6b8"])

    # TODO(cmaloney): More comprehensive testing of the validation checks
    valid_active_set(repository.load_packages(active))


def test_load_bad(repository):
    with pytest.raises(ValueError):
        repository.load_packages(["invalid-package"])


def test_load_nonexistant(repository):
    with pytest.raises(package.exceptions.PackageError):
        repository.load_packages(["Not a package"])
