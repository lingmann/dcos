import os
from subprocess import check_call


def test_bootstrap(tmpdir):
    check_call(["pkgpanda",
        "bootstrap",
        "--root={0}/root".format(tmpdir),
        "--repository=../tests/resources/packages",
        "--config-dir=resources/etc-active"
        ])
    # TODO(cmaloney): Validate things got placed correctly.

# TODO(cmaloney): Test a full OS bootstrap using http://0pointer.de/blog/projects/changing-roots.html
