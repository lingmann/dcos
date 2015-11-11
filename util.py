import jinja2
import os
import shutil
from datetime import datetime
from subprocess import check_output


jinja_env = jinja2.Environment(undefined=jinja2.StrictUndefined)

dcos_image_commit = os.getenv('DCOS_IMAGE_COMMIT', None)

if dcos_image_commit is None:
    dcos_image_commit = check_output(['git', 'rev-parse', 'HEAD']).decode('utf-8').strip()

if dcos_image_commit is None:
    raise "Unable to set dcos_image_commit from teamcity or git."

template_generation_date = str(datetime.utcnow())


def cluster_to_extra_packages(cluster_packages):
    return [pkg['id'] for pkg in cluster_packages.values()]


def try_makedirs(path):
    try:
        os.makedirs(path)
    except FileExistsError:
        pass


def copy_makedirs(src, dest):
    try_makedirs(os.path.dirname(dest))
    shutil.copy(src, dest)


def do_bundle_onprem(extra_files, gen_out, output_dir):
    # We are only being called via dcos_generate_config.sh with an output_dir
    assert output_dir is not None
    assert output_dir
    assert output_dir[-1] != '/'
    output_dir = output_dir + '/'

    # Copy the extra_files
    for filename in extra_files:
        shutil.copy(filename, output_dir + filename)

    # Copy the cluster packages
    for name, info in gen_out.cluster_packages.items():
        copy_makedirs(info['filename'], output_dir + info['filename'])
