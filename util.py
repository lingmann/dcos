import jinja2
import os
import shutil
from datetime import datetime
from subprocess import check_call, check_output
from tempfile import TemporaryDirectory


jinja_env = jinja2.Environment(
        undefined=jinja2.StrictUndefined)

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


def do_bundle_onprem(extra_files, gen_out, output_dir=None):
    # Make a directory for assembling the output
    with TemporaryDirectory(prefix='dcos_gen') as directory:

        # Copy in the extra_files
        for filename in extra_files:
            shutil.copy(filename, directory + '/' + filename)

        for name, info in gen_out.cluster_packages.items():
            copy_makedirs(info['filename'], directory + "/" + info['filename'])

        # Download and place the bootstrap tarball
        # Download to ~/packages/{}.tar.xz then copy so that downloads can be cached.
        bootstrap_id = gen_out.arguments['bootstrap_id']
        local_bootstrap_path = "packages/{}.bootstrap.tar.xz".format(bootstrap_id)
        if not os.path.exists(local_bootstrap_path):
            try:
                check_call([
                    "curl",
                    "-fsSL",
                    "-o",
                    local_bootstrap_path,
                    "https://downloads.mesosphere.com/dcos/{}/bootstrap/{}.bootstrap.tar.xz".format(
                        gen_out.arguments['channel_name'],
                        gen_out.arguments['bootstrap_id'])
                    ])
            except:
                os.remove(local_bootstrap_path)
                raise
        # Copy the tarball in to the artifacts
        copy_makedirs(local_bootstrap_path, directory + "/bootstrap/{}.bootstrap.tar.xz".format(bootstrap_id))

        if output_dir:
            # Write contents directly to output_dir
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            check_call('/bin/cp -r * "{}"'.format(output_dir), cwd=directory, shell=True)
        else:
            # Create a tarball
            check_call(["tar", "-czf", "onprem.tar.xz", "-C", directory, "."])
