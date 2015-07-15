import os
from datetime import datetime
from subprocess import check_call, check_output
from pkgpanda.util import load_string

dcos_image_commit = os.getenv('DCOS_IMAGE_COMMIT', None)

if dcos_image_commit is None:
    dcos_image_commit = check_output(['git', 'rev-parse', 'HEAD']).decode('utf-8').strip()

if dcos_image_commit is None:
    raise "Unable to set dcos_image_commit from teamcity or git."

template_generation_date = str(datetime.utcnow())


def build_packages():
    # TODO(cmaloney): don't shell out.
    check_call(['mkpanda', 'tree', '--mkbootstrap'], cwd='packages', env=os.environ)
    return load_string('packages/bootstrap.latest')


def get_local_build(skip_build):
    if not skip_build:
        return build_packages()
    else:
        return load_string('packages/bootstrap.latest')
