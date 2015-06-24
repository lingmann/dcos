import os
import os.path
import shutil
import sys
from subprocess import check_call


def remove_service(cloud_config, name):
    # Keep track of pre + post length to track if we removed one service and only
    # one service.
    service_count = len(cloud_config['coreos']['units'])
    cloud_config['coreos']['units'] = filter(
            lambda service: service.name != name,
            cloud_config['coreos']['units'])

    new_service_count = len(cloud_config['coreos']['units'])
    # Check to see that we found and removed exactly one service
    assert new_service_count == service_count - 1

    return cloud_config


def change_file_content(cloud_config, name, new_content, mode=0o644):
    file_count = len(cloud_config['write_files'])
    # Remove old
    cloud_config['write_files'] = filter(
        lambda file: file.name == name)
    new_file_count = len(cloud_config['write_files'])
    # Validate that we found and removed exactly one service
    assert new_file_count == file_count - 1

    # Add the new file
    cloud_config['write_files'].append({
        'name': name,
        'content': new_content,
        'permissions': mode
        })


download_local_mount = """[Unit]
Description=Download the DCOS
ConditionPathExists=!/opt/mesosphere/
[Service]
EnvironmentFile=/etc/mesosphere/setup-flags/bootstrap-id
Type=oneshot
ExecStart=/usr/bin/tar -axf /shared/packages/${BOOTSTRAP_ID}.bootstrap.tar.xz -C /opt/mesosphere
"""


def gen(cloud_config, arguments, utils):

    cloud_config = utils.add_roles(cloud_config, ['master', 'slave'])
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
