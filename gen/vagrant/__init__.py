import os
import os.path
import shutil
import sys
from subprocess import check_call


def gen(cloud_config, arguments, utils):

    cloud_config = utils.add_roles(cloud_config, ['master', 'slave', 'vagrant'])
    cloud_config = utils.add_services(cloud_config)

    cluster_name = arguments['cluster_name']
    cluster_folder = "vagrant/cluster/{}".format(cluster_name)

    if os.path.exists(cluster_folder):
        print("ERROR: Cluster {} already exists".format(cluster_name) + ". "
              "To rebuild a cluster with that name run 'vagrant destroy' in " +
              "the cluster folder than `rm -rf` the folder and run this " +
              "script."" Cluster folder: '{}'".format(cluster_folder))
        sys.exit(1)

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
        f.write(utils.render_cloudconfig(cloud_config))

    print("Vagrant cluster ready to launch.")
    print("Launch with:")
    print("$ cd {}; vagrant up".format(cluster_folder))
