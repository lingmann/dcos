import os.path
from shutil import copytree
from subprocess import check_call


def test_build_mesos(tmpdir):
    copytree("resources/mesos", os.path.join(str(tmpdir), "workspace"))
    with tmpdir.join("workspace").as_cwd():
        check_call(["mkpanda"])

    # TODO(cmaloney): Check the package exists with the right contents.
