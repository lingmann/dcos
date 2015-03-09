from util import run


list_output = """mesos--0.22.0
mesos-config--ffddcfb53168d42f92e4771c6f8a8a9a818fd6b8
"""

active_output = """mesos--0.22.0
mesos-config--ffddcfb53168d42f92e4771c6f8a8a9a818fd6b8
"""


def test_list():
    assert run(["pkgpanda", "list", "--repository=../tests/resources/packages"]) == list_output


def test_active():
    assert run(["pkgpanda", "active", "--root=../tests/resources/install"]) == active_output
