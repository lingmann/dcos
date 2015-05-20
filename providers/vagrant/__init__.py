from cloud_config_parameters import CloudConfigParameters

import os
import os.path
import shutil
import sys
from subprocess import check_call

s3_url = 'https://downloads.mesosphere.io/dcos/{}'


class Parameters(CloudConfigParameters):

    def __init__(self, cluster_name, release_name):
        self._cluster_name = cluster_name
        self._release_name = release_name

    @property
    def extra_files_base(self):
        return """  - path: /etc/resolv.conf
    content: 'nameserver 8.8.8.8'
  - path: /etc/mesosphere/setup-packages/dcos-config--setup/etc/cloudenv
    content: |
      MASTER_ELB=127.0.0.1
      ZOOKEEPER_CLUSTER_SIZE=1
      FALLBACK_DNS=8.8.8.8
      MARATHON_HOSTNAME=$private_ipv4
      MESOS_HOSTNAME=$private_ipv4
      MESOS_IP=$private_ipv4
  - path: /etc/mesosphere/setup-packages/dcos-config--setup/etc/exhibitor
    content: |
      EXHIBITOR_FSCONFIGDIR=/var/run/exhibitor
      EXHIBITOR_WEB_UI_PORT=8181
      EXHIBITOR_HOSTNAME=$private_ipv4
""".format(self._cluster_name)

    @property
    def stack_name(self):
        return self._cluster_name

    @property
    def early_units(self):
        return ""

    @property
    def config_writer(self):
        return """    - name: config-writer.service
      command: start
      content: |
        [Unit]
        Description=Write out dynamic config values
        [Service]
        Type=oneshot
        EnvironmentFile=/etc/environment
        # Marathon depends on `hostname` resolution working
        ExecStart=/usr/bin/bash -c "echo ${COREOS_PRIVATE_IPV4} $(hostname) > /etc/hosts"
"""

    @property
    def late_units_base(self):
        return ""

    def GetParameter(self, name):
        return {
            'bootstrap_url': s3_url.format(self._release_name),
            'master_quorum': '1',
            'stack_name': self.stack_name,
            'fallback_dns': '8.8.8.8'
        }[name]

    def AddTestclusterEphemeralVolume(self):
        raise NotImplementedError()

    resolvers = ["8.8.8.8", "8.8.4.4"]
    roles = ["master", "slave"]


def gen(release_name, cluster_name, cloudconfig_render_func, copy_files):

    cluster_folder = "vagrant/cluster/{}".format(cluster_name)

    if os.path.exists(cluster_folder):
        print("ERROR: Cluster {} already exists".format(cluster_name) + "To " +
              "create a new cluster with that name 'vagrant destroy' in the " +
              "cluster folder than gen a new cluster config. Cluster folder: " +
              "'{}'".format(cluster_folder))
        sys.exit(1)

    # Gen the cloud-config
    params = Parameters(cluster_name, release_name)
    cloud_config = cloudconfig_render_func(params)

    # Copy the vagrant-specific stuff
    # Make folder for the cluster-specific files
    check_call(['mkdir', '-p', cluster_folder])

    def copy(name):
        src_path = os.getcwd() + '/vagrant/' + name
        dest_path = cluster_folder + '/' + name
        if copy_files:
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
