from package.kinds import Package

"""Test various kinds of packages work"""


def test_kind_registration():
    assert Package.kinds.keys() == set(["mesos", "module", "config"])
