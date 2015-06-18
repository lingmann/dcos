import os
import os.path
import shutil
import sys
from subprocess import check_call

s3_url = 'https://downloads.mesosphere.io/dcos/{}'

roles = ["master", "slave"]


def gen(cloud_config, config_package_filename, arguments):
    cluster_name = arguments['cluster_name']
    cluster_folder = "vagrant/cluster/{}".format(cluster_name)

    if os.path.exists(cluster_folder):
        print("ERROR: Cluster {} already exists".format(cluster_name) + ". "
              "To rebuild a cluster with that name run 'vagrant destroy' in " +
              "the cluster folder than `rm -rf` the folder and run this " +
              "script."" Cluster folder: '{}'".format(cluster_folder))
        sys.exit(1)

    # Copy the vagrant-specific stuff
    # Make folder for the cluster-specific files
    check_call(['mkdir', '-p', cluster_folder])

    def copy(name):
        src_path = os.getcwd() + '/vagrant/' + name
        dest_path = cluster_folder + '/' + name
        if arguments['copy_files']:
            shutil.copyfile(src_path, dest_path)
        else:
            os.symlink(src_path, dest_path)

    copy("Vagrantfile")
    copy("config.rb")

    with open(cluster_folder + '/user-data', 'w') as f:
        f.write(cloud_config)

    print("Vagrant cluster ready to launch.")
    print("Launch with:")
    print("$ cd {}; vagrant up".format(cluster_folder))
