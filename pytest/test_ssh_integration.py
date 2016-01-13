import asyncio
import getpass
import os
import random
import socket
import subprocess
import threading
import time
import uuid

import pkgpanda.util
import pytest

from ssh.ssh_runner import CommandChain, MultiRunner

sshd_config = [
    'Protocol 1,2',
    'RSAAuthentication yes',
    'PubkeyAuthentication yes',
    'StrictModes no'
]


def start_random_sshd_servers(count, workspace):
    # Get unique number of vailable TCP ports on the system
    sshd_ports = []
    for try_port in random.sample(range(10000, 11000), count):
        while not is_free_port(try_port):
            try_port += 1
        sshd_ports.append(try_port)

    # Run sshd servers in parallel
    for sshd_server_index in range(count):
        t = threading.Thread(target=create_ssh_server, args=(sshd_ports[sshd_server_index], workspace))
        t.start()
    return sshd_ports


def is_free_port(port):
    sock = socket.socket()
    try:
        sock.connect(('127.0.0.1', port))
        return False
    except socket.error:
        return True


def create_ssh_server(port, workspace):
    try:
        subprocess.check_call(['/usr/sbin/sshd', '-p{}'.format(port), '-f{}'.format(workspace + '/sshd_config'), '-d'])
    except subprocess.CalledProcessError:
        pass


def generate_fixtures(workspace):
    subprocess.check_call(['ssh-keygen', '-f', workspace + '/host_key', '-t', 'rsa', '-N', ''])

    local_sshd_config = sshd_config.copy()
    local_sshd_config.append('AuthorizedKeysFile {}'.format(workspace + '/host_key.pub'))
    local_sshd_config.append('HostKey {}'.format(workspace + '/host_key'))

    with open(workspace + '/sshd_config', 'w') as fh:
        fh.writelines(['{}\n'.format(line) for line in local_sshd_config])

    assert os.path.isfile(os.path.join(workspace, 'host_key'))
    assert os.path.isfile(os.path.join(workspace, 'host_key.pub'))
    assert os.path.isfile(os.path.join(workspace, 'sshd_config'))


@pytest.yield_fixture
def loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


def test_ssh(tmpdir, loop):
    workspace = tmpdir.strpath
    generate_fixtures(workspace)
    sshd_ports = start_random_sshd_servers(20, workspace)

    # wait a little bit for sshd server to start
    time.sleep(3)
    runner = MultiRunner(['127.0.0.1:{}'.format(port) for port in sshd_ports], workspace, ssh_user=getpass.getuser(),
                         ssh_key_path=workspace + '/host_key')
    host_port = ['127.0.0.1:{}'.format(port) for port in sshd_ports]

    chain = CommandChain('test')
    chain.add_execute_cmd('uname -a')
    try:
        results = loop.run_until_complete(runner.run_commands_chain_async(chain, block=True))
    finally:
        loop.close()

    assert len(results) == 20
    for host_result in results:
        for command_result in host_result:
            for host, process_result in command_result.items():
                assert process_result['returncode'] == 0, process_result['stderr']
                assert host in host_port
                assert '/usr/bin/ssh' in process_result['cmd']
                assert 'uname' in process_result['cmd']


def test_scp_remote_to_local(tmpdir, loop):
    workspace = tmpdir.strpath
    generate_fixtures(workspace)
    sshd_ports = start_random_sshd_servers(1, workspace)

    # wait a little bit for sshd server to start
    time.sleep(1)

    id = uuid.uuid4().hex
    pkgpanda.util.write_string(workspace + '/pilot.txt', id)
    runner = MultiRunner(['127.0.0.1:{}'.format(port) for port in sshd_ports], workspace, ssh_user=getpass.getuser(),
                         ssh_key_path=workspace + '/host_key')
    host_port = ['127.0.0.1:{}'.format(port) for port in sshd_ports]

    chain = CommandChain('test')
    chain.add_copy_cmd(workspace + '/pilot.txt.copied', workspace + '/pilot.txt', remote_to_local=True)
    try:
        copy_results = loop.run_until_complete(runner.run_commands_chain_async(chain, block=True))
    finally:
        loop.close()

    assert len(copy_results) == 1
    assert os.path.isfile(workspace + '/pilot.txt.copied')
    assert pkgpanda.util.load_string(workspace + '/pilot.txt.copied') == id
    for host_result in copy_results:
            for command_result in host_result:
                for host, process_result in command_result.items():
                    assert process_result['returncode'] == 0, process_result['stderr']
                    assert host in host_port
                    assert '/usr/bin/scp' in process_result['cmd']
                    assert workspace + '/pilot.txt.copied' in process_result['cmd']


def test_scp(tmpdir, loop):
    workspace = tmpdir.strpath
    generate_fixtures(workspace)
    sshd_ports = start_random_sshd_servers(1, workspace)

    # wait a little bit for sshd server to start
    time.sleep(1)

    id = uuid.uuid4().hex
    pkgpanda.util.write_string(workspace + '/pilot.txt', id)
    runner = MultiRunner(['127.0.0.1:{}'.format(port) for port in sshd_ports], workspace, ssh_user=getpass.getuser(),
                         ssh_key_path=workspace + '/host_key')
    host_port = ['127.0.0.1:{}'.format(port) for port in sshd_ports]

    chain = CommandChain('test')
    chain.add_copy_cmd(workspace + '/pilot.txt', workspace + '/pilot.txt.copied')
    try:
        copy_results = loop.run_until_complete(runner.run_commands_chain_async(chain, block=True))
    finally:
        loop.close()

    assert len(copy_results) == 1
    assert os.path.isfile(workspace + '/pilot.txt.copied')
    assert pkgpanda.util.load_string(workspace + '/pilot.txt.copied') == id
    for host_result in copy_results:
            for command_result in host_result:
                for host, process_result in command_result.items():
                    assert process_result['returncode'] == 0, process_result['stderr']
                    assert host in host_port
                    assert '/usr/bin/scp' in process_result['cmd']
                    assert workspace + '/pilot.txt' in process_result['cmd']


def test_scp_recursive(tmpdir, loop):
    workspace = tmpdir.strpath
    generate_fixtures(workspace)
    sshd_ports = start_random_sshd_servers(1, workspace)

    # wait a little bit for sshd server to start
    time.sleep(1)

    id = uuid.uuid4().hex
    pkgpanda.util.write_string(workspace + '/recursive_pilot.txt', id)
    runner = MultiRunner(['127.0.0.1:{}'.format(port) for port in sshd_ports], workspace, ssh_user=getpass.getuser(),
                         ssh_key_path=workspace + '/host_key')
    host_port = ['127.0.0.1:{}'.format(port) for port in sshd_ports]

    chain = CommandChain('test')
    chain.add_copy_cmd(workspace + '/recursive_pilot.txt', workspace + '/recursive_pilot.txt.copied', recursive=True)
    try:
        copy_results = loop.run_until_complete(runner.run_commands_chain_async(chain, block=True))
    finally:
        loop.close()

    dest_path = workspace + '/recursive_pilot.txt.copied'
    assert os.path.exists(dest_path)
    assert os.path.isfile(dest_path)
    assert len(copy_results) == 1
    assert pkgpanda.util.load_string(dest_path) == id
    for host_result in copy_results:
            for command_result in host_result:
                for host, process_result in command_result.items():
                    assert process_result['returncode'] == 0, process_result['stderr']
                    assert host in host_port
                    assert '/usr/bin/scp' in process_result['cmd']
                    assert '-r' in process_result['cmd']
                    assert workspace + '/recursive_pilot.txt' in process_result['cmd']
