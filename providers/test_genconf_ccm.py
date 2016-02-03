#!/usr/bin/env python3
"""Integration test for SSH installer with CCM provided VPC
by shelling out to installed genconf python app

REQUIREMENTS:
    dcos_generate_config.sh artifact is in current working dir
"""
import os
import random
import stat
import string
import subprocess
import sys
import time
from copy import copy

import pkg_resources
import yaml
from retrying import retry

import providers.ccm
from deploy.console_printer import clean_logs, print_failures
from ssh.ssh_runner import SSHRunner


def run_cmd(mode, expect_errors=False):
    print("Running: dcos_generate_config with mode", mode)
    # NOTE: We use `bash` as a wrapper here to make it so dcos_generate_config.sh
    # doesn't have to be executable.
    cmd = ['bash', './dcos_generate_config.sh', '--log-level', 'debug', mode]
    p = subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    out = p.communicate()[1].decode()
    # TODO(cmaloney): Only print on an error.
    print(out)
    if expect_errors:
        assert p.returncode != 0, "{} exited with error code {} (success), but expected an error.".format(
            mode, p.returncode)
    else:
        assert p.returncode == 0, "{} exited with error code {}".format(mode, p.returncode)
        assert "Errors encountered" not in out, "Errors encountered in running {}".format(mode)


def make_vpc():
    print("Spinning up AWS VPC via CCM")
    random_identifier = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(10))
    unique_cluster_id = "installer-test-{}".format(random_identifier)
    ccm = providers.ccm.Ccm()
    vpc = ccm.create_vpc(
        name=unique_cluster_id,
        time=60,
        instance_count=3,
        instance_type="m3.large",
        instance_os="cent-os-7",
        key_pair_name=unique_cluster_id
        )
    vpc.wait_for_up()
    host_list = vpc.hosts()
    if len(host_list) == 0:
        print("VPC failed to spin up!")
        vpc.delete()
        sys.exit(1)

    # Write out the ssh key to the local filesystem for the ssh lib to pick up.
    with open("ssh_key", "w") as ssh_key_fh:
        ssh_key_fh.write(vpc.get_ssh_key())

    return vpc


def get_local_addresses(ssh_runner):
    '''integration_test.py needs local IP addresses
    '''
    mapping = {}
    postfix = copy(ssh_runner.log_postfix)
    ssh_runner.log_postfix = 'ip'
    ssh_runner.execute_cmd("curl -fsSL http://169.254.169.254/latest/meta-data/local-ipv4")
    for host in ssh_runner.targets:
        with open("{}/{}_{}.log".format(ssh_runner.log_directory, host, 'ip'), 'r') as yaml_fh:
            host_data = yaml.load(yaml_fh)
        for timestamp, values in host_data[host].items():
            mapping[host] = values['stdout'][0]
    ssh_runner.log_postfix = postfix
    return mapping


def setup_docker_registry(ssh_runner):
    targets = copy(ssh_runner.targets)
    postfix = copy(ssh_runner.log_postfix)
    ssh_runner.targets = targets[1:]
    ssh_runner.log_postfix = 'registry_setup'
    clean_logs(ssh_runner.log_postfix, ssh_runner.log_directory)
    print("Setting up test server docker app and registry on all hosts")
    print("Copying setup files")
    ssh_runner.execute_cmd('rm -rf /home/centos/test_server')
    ssh_runner.execute_cmd('mkdir -p /home/centos/test_server')
    test_server_docker = pkg_resources.resource_filename(__name__, "../docker/test_server/Dockerfile")
    ssh_runner.copy_cmd(test_server_docker, '/home/centos/test_server/Dockerfile')
    test_server_script = pkg_resources.resource_filename(__name__, "../docker/test_server/test_server.py")
    ssh_runner.copy_cmd(test_server_script, '/home/centos/test_server/test_server.py')
    print("Starting docker registry")
    ssh_runner.execute_cmd('docker run -d -p 5000:5000 --restart=always --name registry registry:2')
    print("Building dockerized test server")
    ssh_runner.execute_cmd('cd /home/centos/test_server && docker build -t 127.0.0.1:5000/test_server .')
    print("Push test server to registry")
    ssh_runner.execute_cmd('docker push 127.0.0.1:5000/test_server')
    print_failures(ssh_runner.log_postfix, ssh_runner.log_directory)
    ssh_runner.targets = targets
    ssh_runner.log_postfix = postfix


def setup_pytest(ssh_runner):
    targets = copy(ssh_runner.targets)
    postfix = copy(ssh_runner.log_postfix)
    ssh_runner.targets = [targets[0]]
    ssh_runner.log_postfix = 'pytest_setup'
    clean_logs(ssh_runner.log_postfix, ssh_runner.log_directory)
    # Get the stuff there
    print("Cleaning out old dirs")
    ssh_runner.execute_cmd('rm -rf /home/centos/py.test')
    ssh_runner.execute_cmd('mkdir -p /home/centos/py.test')
    print("Copy files")
    pytest_docker = pkg_resources.resource_filename(__name__, "../docker/py.test/Dockerfile")
    ssh_runner.copy_cmd(pytest_docker, '/home/centos/py.test/Dockerfile')
    test_script = pkg_resources.resource_filename(__name__, '../integration_test.py')
    ssh_runner.copy_cmd(test_script, '/home/centos/integration_test.py')
    print("Building docker py.test")
    ssh_runner.execute_cmd('cd /home/centos/py.test && docker build -t py.test .')
    print_failures(ssh_runner.log_postfix, ssh_runner.log_directory)
    ssh_runner.targets = targets
    ssh_runner.log_postfix = postfix


def integration_test(ssh_runner):
    setup_docker_registry(ssh_runner)
    setup_pytest(ssh_runner)
    local_ip = get_local_addresses(ssh_runner)
    print("Running legacy integration test")
    targets = copy(ssh_runner.targets)
    postfix = copy(ssh_runner.log_postfix)
    ssh_runner.targets = [targets[0]]
    ssh_runner.log_postfix = 'pytest'
    clean_logs(ssh_runner.log_postfix, ssh_runner.log_directory)
    # Run integration_test.py against new cluster
    test_cmd = """
docker run \
-v /home/centos/integration_test.py:/integration_test.py \
-e "DCOS_DNS_ADDRESS=http://{dcos_dns}" \
-e "MASTER_HOSTS={master_list}" \
-e "SLAVE_HOSTS={slave_list}" \
-e "REGISTRY_HOST=127.0.0.1" \
-e "DNS_SEARCH=true" \
--net=host py.test py.test -vv /integration_test.py \
""".format(
        dcos_dns=local_ip[targets[1]],
        master_list=local_ip[targets[1]],
        slave_list=",".join([local_ip[_] for _ in targets[2:]]),
        registry_host=targets[0])
    print("Running test in remote docker")
    ssh_runner.execute_cmd(test_cmd)
    test_log_file = "{}/{}_{}.log".format(ssh_runner.log_directory, ssh_runner.targets[0], 'pytest')
    with open(test_log_file, 'r') as yaml_fh:
        host_data = yaml.load(yaml_fh)
        for timestamp, values in host_data[ssh_runner.targets[0]].items():
            for line in values['stdout']:
                print(line)
    # Will exit as error if return code is nonzero
    print_failures(ssh_runner.log_postfix, ssh_runner.log_directory)
    ssh_runner.targets = targets
    ssh_runner.log_postfix = postfix


def prep_hosts(ssh_runner):
    # TODO(mellenburg): replace setup with --preflightfix functionality
    ssh_runner.execute_cmd("sudo yum install -y tar xz unzip curl", True)
    ssh_runner.execute_cmd("sudo curl -sSL https://get.docker.com/ | sh", True)
    ssh_runner.execute_cmd("sudo service docker start", True)
    ssh_runner.execute_cmd("sudo groupadd nogroup", True)
    ssh_runner.execute_cmd("sudo usermod -aG docker centos", True)

    targets = copy(ssh_runner.targets)

    # Setup and start the first host in the list only as the bootstrap ZK.
    ssh_runner.targets = [targets[0]]
    ssh_runner.execute_cmd("docker run -d -p 2181:2181 -p 2888:2888 -p 3888:3888 jplock/zookeeper")

    # Restore the target list for future ssh_runner users
    ssh_runner.targets = targets


def main():
    # Local dcos_generate_config.sh file must exist
    assert os.path.exists('dcos_generate_config.sh')

    # The genconf folder must be already cleaned up. Can't be cleaned here
    # because it will likely be owned by root.
    # TODO(cmaloney): Make it so we don't make any root owned directories by
    # making sure to always mkdir before doing a docker volume mount.
    assert not os.path.exists("genconf")
    os.makedirs("genconf")

    host_list = None
    if 'CCM_VPC_HOSTS' in os.environ:
        host_list = os.environ['CCM_VPC_HOSTS'].split(',')
    # host_list array can be passed to use pre-existing VPC
    if 'CCM_HOST_SETUP' in os.environ:
        assert os.environ['CCM_HOST_SETUP'] in ['true', 'false']
    do_setup = os.getenv('CCM_HOST_SETUP', 'true') == 'true'

    vpc = None  # Set if the test owns the VPC

    if host_list is None:
        vpc = make_vpc()

        @retry(wait_fixed=1000, stop_max_attempt_number=100)
        def get_hosts():
            return vpc.hosts()

        host_list = get_hosts()
        # TODO(cmaloney): Use the ssh runner and retrying to do this same thing more reliably.
        # There is some significant latency between an AWS node is created and when the access
        # is enabled. Wait to make sure that deploy lib will not be prompted for password
        print("Sleep for 60 seconds so authorized_keys is populated on hosts...")

        # TODO(cmaloney):
        time.sleep(60)

    # Make the SSH key accessible to dcos_generate_config.sh by putting it into
    # the genconf folder. Since the genconf folder is always removed / cleaned
    # out when running the test, this allows sharing keys between runs of the
    # test / using pre-provisioned clusters.
    assert os.path.exists("ssh_key")
    subprocess.check_call(['cp', 'ssh_key', 'genconf/ssh_key'])
    os.chmod("genconf/ssh_key", stat.S_IREAD | stat.S_IWRITE)

    print("VPC host(s): {}".format(host_list))
    # use first node as zk backend, second node as master, all others as slaves

    # before real config is written, try running genconf to make sure it fails
    run_cmd("--genconf", expect_errors=True)
    # Now create a real config
    test_config = {
        "cluster_config": {
            "cluster_name": "SSH Installed DCOS",
            "bootstrap_url": "file:///opt/dcos_install_tmp",
            "dns_search": "mesos",
            "docker_remove_delay": "1hrs",
            "exhibitor_storage_backend": "zookeeper",
            "exhibitor_zk_hosts": host_list[0]+":2181",
            "exhibitor_zk_path": "/exhibitor",
            "gc_delay": "2days",
            "master_discovery": "static",
            "master_list": [host_list[1]],
            "resolvers": ["8.8.8.8", "8.8.4.4"],
            "roles": "slave_public",
            "weights": "slave_public=1"
            },
        "ssh_config": {
            "ssh_user": "centos",
            "ssh_port": 22,
            "ssh_key_path": "/genconf/ssh_key",
            # skip exhibitor_zk_host
            "target_hosts": host_list[1:],
            "log_directory": "/genconf/",
            "process_timeout": 1200
            }
        }
    with open("genconf/config.yaml", "w") as config_fh:
        config_fh.write(yaml.dump(test_config))
    with open("genconf/ip-detect", "w") as ip_detect_fh:
        ip_detect_fh.write("#!/bin/bash\ncurl -fsSL http://169.254.169.254/latest/meta-data/local-ipv4")

    assert os.path.exists("genconf/ssh_key")
    # Create custom SSH Runnner to setup the nodes for install
    ssh_runner = SSHRunner()
    ssh_runner.ssh_key_path = "genconf/ssh_key"
    ssh_runner.ssh_user = test_config["ssh_config"]["ssh_user"]
    ssh_runner.log_directory = "genconf"
    ssh_runner.process_timeout = 1200
    ssh_runner.targets = host_list

    # Run Configuratator
    run_cmd('--genconf')
    if do_setup:
        # Check that --preflight gives an error
        run_cmd('--preflight', expect_errors=True)

        # Prep the hosts
        prep_hosts(ssh_runner)

    # Run Preflight Checks
    run_cmd('--preflight')

    # Run Deploy Process
    run_cmd('--deploy')

    # Retry postflight for a while until it passes.
    @retry(wait_fixed=1000, stop_max_attempt_number=100)
    def postflight():
        run_cmd('--postflight')

    postflight()

    # Runs dcos-image/integration_test.py inside the cluster
    integration_test(ssh_runner)

    # TODO(cmaloney): add a `--healthcheck` option which runs dcos-diagnostics
    # on every host to see if they are working.

    # Delete the cluster if all was successful to minimize potential costs.
    # Failed clusters the hosts will continue running
    if vpc is not None:
        vpc.delete()


if __name__ == "__main__":
    main()
