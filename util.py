import os
from datetime import datetime
from pkgpanda.util import load_string
from subprocess import check_call, check_output

dcos_image_commit = os.getenv('DCOS_IMAGE_COMMIT', None)

if dcos_image_commit is None:
    dcos_image_commit = check_output(['git', 'rev-parse', 'HEAD']).decode('utf-8').strip()

if dcos_image_commit is None:
    raise "Unable to set dcos_image_commit from teamcity or git."

template_generation_date = str(datetime.utcnow())


def cluster_to_extra_packages(cluster_packages):
    return [pkg['id'] for pkg in cluster_packages.values()]


def get_local_build(skip_build):
    if not skip_build:
        check_call(['mkpanda', 'tree', '--mkbootstrap'], cwd='packages', env=os.environ)
        return load_string('packages/bootstrap.latest')

    return load_string('packages/bootstrap.latest')
