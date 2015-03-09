"""Test functionality of the local package repository"""

import pkgpanda.exceptions
from pkgpanda import Repository

import pytest


@pytest.fixture
def repository():
    return Repository("resources/packages")


def test_list(repository):
    packages = repository.list()
    assert type(packages) is set
    assert packages == set(
        ['mesos-config--ffddcfb53168d42f92e4771c6f8a8a9a818fd6b8', 'mesos--0.22.0', "invalid-package"])


def test_load_bad(repository):
    with pytest.raises(pkgpanda.exceptions.PackageError):
        repository.load_packages(["invalid-package"])


def test_load_nonexistant(repository):
    with pytest.raises(pkgpanda.exceptions.PackageError):
        repository.load_packages(["Not a package"])
