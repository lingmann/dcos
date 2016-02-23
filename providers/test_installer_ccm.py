#!/usr/bin/env python3
"""Integration test for SSH installer with CCM provided VPC
by shelling out to installed genconf python app

REQUIREMENTS:
    dcos_generate_config.sh artifact is in current working dir
"""
import asyncio
import logging
import multiprocessing
import os
import random
import stat
import string
import subprocess

import pkg_resources
import yaml
from retrying import retry

import providers.ccm
from ssh.ssh_runner import MultiRunner
from ssh.utils import CommandChain, SyncCmdDelegate

variant_config_generators = {
    'default': 'dcos_generate_config.sh',
    'ee': 'dcos_generate_config.ee.sh'
}


def run_cmd(mode, expect_errors=False):
    if 'DCOS_VARIANT' in os.environ:
        variant = os.environ['DCOS_VARIANT']
    else:
        variant = 'default'
    print("Running: dcos_generate_config with mode: {} and variant: {}".format(mode, variant))
    # NOTE: We use `bash` as a wrapper here to make it so dcos_generate_config.sh
    # doesn't have to be executable.
    cmd = ['bash', './{}'.format(variant_config_generators[variant]), mode]

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


def pkg_filename(relative_path):
    return pkg_resources.resource_filename(__name__, relative_path)


def run_loop(ssh_runner, chain):
    # TODO: replace with SSH Library Synchronous API

    def function():
        result = yield from ssh_runner.run_commands_chain_async([chain], block=True)
        return result

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(function())
    finally:
        loop.close()
    return result


def check_results(results, force_print=False):
    """Loops through iterable results. Only one result dict is produced per
    command, so when iterating, pop the only dict rather than iterate over it

    Args:
        results: output of loop.run_until_complete(runner.run_commands_chain_async([cmd_chain]))
        force_print: print output from loop even if it was successful

    Raises:
        AssertionError: if any of the commands have non-zero return code
    """
    for host_result in results:
        for command_result in host_result:
            assert len(command_result.keys()) == 1, 'SSH Library returned unexpected result format'
            host, data = command_result.popitem()
            err_msg = "Host {} returned exit code {} after running {}\nSTDOUT: {}\nSTDERR: {}"
            assert data['returncode'] == 0, err_msg.format(
                    host, data['returncode'], data['cmd'], '\n'.join(data['stdout']), '\n'.join(data['stderr']))
            if force_print:
                print(err_msg.format(
                    host, data['returncode'], data['cmd'], '\n'.join(data['stdout']), '\n'.join(data['stderr'])))


@retry(wait_fixed=1000, stop_max_delay=1000*300)
def get_local_addresses(ssh_runner, remote_dir):
    """Uses checked-in IP detect script to report local IP mapping
    Also functions as a test to verify cluster is up and accessible

    Args:
        ssh_runner: instance of ssh.ssh_runner.MultiRunner
        remote_dir (str): path on hosts for ip-detect to be copied and run in

    Returns:
        dict[public_IP] = local_IP
    """

    def remote(path):
        return remote_dir + '/' + path

    ip_detect_script = pkg_filename('../scripts/ip-detect/aws.sh')
    ip_map_chain = CommandChain('ip_map')
    ip_map_chain.add_copy(ip_detect_script, remote('ip-detect.sh'))
    ip_map_chain.add_execute(['bash', remote('ip-detect.sh')])
    mapping = {}
    result = run_loop(ssh_runner, ip_map_chain)
    for host_result in result:
        host, data = host_result[-1].popitem()  # Grab the last command trigging the script
        assert data['returncode'] == 0
        local_ip = data['stdout'][0].rstrip()
        assert local_ip != ''
        mapping[host.split(":")[0]] = local_ip
    return mapping


def break_prereqs(ssh_runner):
    """Performs commands that will cause preflight to fail on a prepared node

    Args:
        ssh_runner: instance of ssh.ssh_runner.MultiRunner
    """
    break_prereq_chain = CommandChain('break_prereqs')
    break_prereq_chain.add_execute(['sudo', 'groupdel', 'nogroup'])

    check_results(run_loop(ssh_runner, break_prereq_chain))


def test_setup(ssh_runner, registry, remote_dir):
    """Transfer resources and issues commands on host to build test app,
    host it on a docker registry, and prepare the integration_test container

    Args:
        ssh_runner: instance of ssh.ssh_runner.MultiRunner
        registry (str): address of registry host that is visible to test nodes
        remote_dir (str): path to be used for setup and file transfer on host

    Returns:
        result from async chain that can be checked later for success
    """
    test_server_docker = pkg_filename('../docker/test_server/Dockerfile')
    test_server_script = pkg_filename('../docker/test_server/test_server.py')
    pytest_docker = pkg_filename('../docker/py.test/Dockerfile')
    test_script = pkg_filename('../integration_test.py')
    test_setup_chain = CommandChain('test_setup')
    # First start bootstrap Zookeeper
    test_setup_chain.add_execute([
        'sudo', 'docker', 'run', '-d', '-p', '2181:2181', '-p', '2888:2888',
        '-p', '3888:3888', 'jplock/zookeeper'])
    # Create test application

    def remote(path):
        return remote_dir + '/' + path

    test_setup_chain.add_execute(['mkdir', '-p', remote('test_server')])
    test_setup_chain.add_copy(test_server_docker, remote('test_server/Dockerfile'))
    test_setup_chain.add_copy(test_server_script, remote('test_server/test_server.py'))
    test_setup_chain.add_execute([
        'docker', 'run', '-d', '-p', '5000:5000', '--restart=always', '--name',
        'registry', 'registry:2'])
    test_setup_chain.add_execute([
        'cd', remote('test_server'), '&&', 'docker', 'build', '-t',
        '{}:5000/test_server'.format(registry), '.'])
    test_setup_chain.add_execute(['docker', 'push', "{}:5000/test_server".format(registry)])
    test_setup_chain.add_execute(['rm', '-rf', remote('test_server')])
    # Create pytest/integration test instance on remote
    test_setup_chain.add_execute(['mkdir', '-p', remote('py.test')])
    test_setup_chain.add_copy(pytest_docker, remote('py.test/Dockerfile'))
    test_setup_chain.add_copy(test_script, remote('integration_test.py'))
    test_setup_chain.add_execute([
        'cd', remote('py.test'), '&&', 'docker', 'build', '-t', 'py.test', '.'])
    test_setup_chain.add_execute(['rm', '-rf', remote('py.test')])

    check_results(run_loop(ssh_runner, test_setup_chain))


def integration_test(
        ssh_runner, dcos_dns, master_list, slave_list, registry_host,
        use_ee, test_minuteman, test_dns_search, ci_flags):
    """Runs integration test on host
    Note: check_results() will raise AssertionError if test fails

    Args:
        ssh_runner: instance of ssh.ssh_runner.MultiRunner
        dcos_dns: string representing IP of DCOS DNS host
        master_list: string of comma separated master addresses
        slave_list: string of comma separated agent addresses
        registry_host: string for address where marathon can pull test app
        use_ee: if set to True then use 'ee' variant artifact, else use default
        test_minuteman: if set to True then test for minuteman service
        test_dns_search: if set to True, test for deployed mesos DNS app
        ci_flags: optional additional string to be passed to test

    """
    marker_args = '-m "not minuteman"'
    if test_minuteman:
        marker_args = ''

    run_test_chain = CommandChain('run_test')
    dns_search = 'true' if test_dns_search else 'false'
    variant = 'ee' if use_ee else ''
    run_test_chain.add_execute([
        'docker', 'run', '-v', '/home/centos/integration_test.py:/integration_test.py',
        '-e', 'DCOS_DNS_ADDRESS=http://'+dcos_dns,
        '-e', 'MASTER_HOSTS='+master_list,
        '-e', 'PUBLIC_MASTER_HOSTS='+master_list,
        '-e', 'SLAVE_HOSTS='+slave_list,
        '-e', 'REGISTRY_HOST='+registry_host,
        '-e', 'DCOS_VARIANT='+variant,
        '-e', 'DNS_SEARCH='+dns_search,
        '--net=host', 'py.test', 'py.test',
        '-vv', ci_flags, marker_args, '/integration_test.py'])

    check_results(run_loop(ssh_runner, run_test_chain), force_print=True)


def prep_hosts(ssh_runner, registry, minuteman_enabled=False):
    """Runs steps so that nodes can pass preflight checks. Nodes are expected
    to either use the custom AMI or have install-prereqs run on them. Additionally,
    Note: break_prereqs is run before this always

    Args:
        ssh_runner: instance of ssh.ssh_runner.MultiRunner
        registry: string to configure hosts with trusted registry for app deployment
        minuteman_enabled: if True, minuteman will be available after DCOS install
    """
    host_prep_chain = CommandChain('host_prep')
    host_prep_chain.add_execute([
        'sudo', 'sed', '-i',
        "'/ExecStart=\/usr\/bin\/docker/ !b; s/$/ --insecure-registry={}:5000/'".format(registry),
        '/etc/systemd/system/docker.service.d/execstart.conf'])
    host_prep_chain.add_execute(['sudo', 'systemctl', 'daemon-reload'])
    host_prep_chain.add_execute(['sudo', 'systemctl', 'restart', 'docker'])
    host_prep_chain.add_execute(['sudo', 'groupadd', '-g', '65500', 'nogroup'])
    host_prep_chain.add_execute(['sudo', 'usermod', '-aG', 'docker', 'centos'])

    if minuteman_enabled:
        host_prep_chain.add_execute(['sudo', 'yum', 'install', '-y', 'ipset'])
        host_prep_chain.add_execute(['sudo', 'mkdir', '-p', '/etc/mesosphere/roles'])
        host_prep_chain.add_execute(['sudo', 'touch', '/etc/mesosphere/roles/minuteman'])

    check_results(run_loop(ssh_runner, host_prep_chain))


def make_vpc():
    print("Spinning up AWS VPC via CCM")
    random_identifier = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(10))
    unique_cluster_id = "installer-test-{}".format(random_identifier)
    ccm = providers.ccm.Ccm()
    vpc = ccm.create_vpc(
        name=unique_cluster_id,
        time=60,
        instance_count=3,
        instance_type="m3.xlarge",
        instance_os="cent-os-7-dcos-prereqs",
        region="us-west-2",
        key_pair_name=unique_cluster_id
        )

    # Write out the ssh key to the local filesystem for the ssh lib to pick up.
    with open("ssh_key", "w") as ssh_key_fh:
        ssh_key_fh.write(vpc.get_ssh_key())

    return vpc


def main():
    logging.basicConfig(level=logging.DEBUG)
    if 'DCOS_VARIANT' in os.environ:
        variant = os.environ['DCOS_VARIANT']
    else:
        variant = 'default'

    # Local dcos_generate_config file for the variant must exist
    assert os.path.exists(variant_config_generators[variant])

    # The genconf folder must be already cleaned up. Can't be cleaned here
    # because it will likely be owned by root.
    assert not os.path.exists('genconf')
    os.makedirs('genconf')

    host_list = None
    if 'CCM_VPC_HOSTS' in os.environ:
        host_list = os.environ['CCM_VPC_HOSTS'].split(',')
    # host_list array can be passed to use pre-existing VPC
    if 'CCM_HOST_SETUP' in os.environ:
        assert os.environ['CCM_HOST_SETUP'] in ['true', 'false']
    do_setup = os.getenv('CCM_HOST_SETUP', 'true') == 'true'

    if 'MINUTEMAN_ENABLED' in os.environ:
        assert os.environ['MINUTEMAN_ENABLED'] in ['true', 'false']
    minuteman_enabled = os.getenv('MINUTEMAN_ENABLED', 'false') == 'true'

    vpc = None  # Set if the test owns the VPC

    if host_list is None:
        vpc = make_vpc()
        host_list = vpc.hosts()

    assert os.path.exists('ssh_key'), 'Valid SSH key for hosts must be in working dir!'
    os.chmod('ssh_key', stat.S_IREAD | stat.S_IWRITE)
    subprocess.check_call(['cp', 'ssh_key', 'genconf/ssh_key'])

    print("VPC hosts: {}".format(host_list))
    # use first node as zk backend, second node as master, all others as slaves
    test_config = {
        "cluster_name": "SSH Installed DCOS",
        "bootstrap_url": "file:///opt/dcos_install_tmp",
        "dns_search": "mesos",
        'ip_detect_path': '/genconf/ip-detect',
        "exhibitor_storage_backend": "zookeeper",
        "exhibitor_zk_hosts": host_list[0]+":2181",
        "exhibitor_zk_path": "/exhibitor",
        "master_discovery": "static",
        "master_list": [host_list[1]],
        "ssh_user": "centos",
        # skip exhibitor_zk_host and master
        "agent_list": host_list[2:],
        "process_timeout": 1200,
        # Must match what is inserted for test_if_authentication_works(), line 328,
        # in integration_test.py
        "superuser_username": 'bootstrapuser',
        # 'deleteme' is cleartext value
        "superuser_password_hash":
            '$6$rounds=656000$oZtCG2k7wQCxXmsU$SgdtyDthOdZzyekzRjVMINQ5pRofFEhlZTq15xhpArDglGdzw3rP9PW2JgSabnfMmY/d2Ciz215uxNgaiyPZG/'  # noqa
    }
    with open("genconf/config.yaml", "w") as config_fh:
        config_fh.write(yaml.dump(test_config))
    with open("genconf/ip-detect", "w") as ip_detect_fh:
        ip_detect_fh.write("#!/bin/bash\ncurl -fsSL http://169.254.169.254/latest/meta-data/local-ipv4")

    # Create custom SSH Runnner to help orchestrate the test
    ssh_user = 'centos'
    ssh_key_path = 'ssh_key'
    remote_dir = '/home/centos'

    def make_runner(host_list):
        return MultiRunner(
                host_list, ssh_user=ssh_user, ssh_key_path=ssh_key_path,
                process_timeout=600, async_delegate=SyncCmdDelegate())

    all_host_runner = make_runner(host_list)
    test_host_runner = make_runner([host_list[0]])

    print('Checking that hosts are accessible')
    local_ip = get_local_addresses(all_host_runner, remote_dir)
    registry_host = local_ip[host_list[0]]
    print("Registry/Test Host Local IP: {}".format(registry_host))

    print('Running configurator')
    run_cmd('--genconf')
    print('Making sure prereqs are broken...')
    break_prereqs(all_host_runner)
    print('Check that --preflight gives an error')
    run_cmd('--preflight', expect_errors=True)

    test_setup_handler = None
    if do_setup:
        print('Prepping all hosts...')
        prep_hosts(all_host_runner, registry=registry_host, minuteman_enabled=minuteman_enabled)
        # This will start up the bootstrap ZK in BG
        print('Setting up test node while deploy runs...')
        # TODO: remove calls to both multiprocessing and asyncio
        # at time of writing block=False only supported for JSON delegates
        test_setup_handler = multiprocessing.Process(
                target=test_setup, args=(test_host_runner, registry_host, remote_dir))
        # Wait for this to finish later as it is not required for deploy and preflight
        test_setup_handler.start()

    # Run Preflight Checks
    run_cmd('--preflight')

    # Run  deploy (takes ~8 minutes)
    run_cmd('--deploy')

    # If we needed setup, wait for it to finish
    if test_setup_handler:
        test_setup_handler.join()

    # Retry postflight for a while until it passes.
    @retry(wait_fixed=1000, stop_max_attempt_number=3)
    def postflight():
        run_cmd('--postflight')

    postflight()

    # Runs dcos-image/integration_test.py inside the cluster
    integration_test(
        test_host_runner,
        dcos_dns=local_ip[host_list[1]],
        master_list=local_ip[host_list[1]],
        slave_list=','.join([local_ip[_] for _ in host_list[2:]]),
        registry_host=registry_host,
        use_ee=True if variant == 'ee' else False,
        # Setting dns_search: mesos not currently supported in API
        test_dns_search=True,
        test_minuteman=minuteman_enabled,
        ci_flags=os.getenv('CI_FLAGS', ''))

    # TODO(cmaloney): add a `--healthcheck` option which runs dcos-diagnostics
    # on every host to see if they are working.

    # Delete the cluster if all was successful to minimize potential costs.
    # Failed clusters the hosts will continue running
    if vpc is not None:
        vpc.delete()


if __name__ == "__main__":
    main()
