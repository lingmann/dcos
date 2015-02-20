from subprocess import check_call


def test_bootstrap():
    check_call(["pkgpanda", "bootstrap", "--root=slave"])
    # TODO(cmaloney): Validate things got placed correctly.