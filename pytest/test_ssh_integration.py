import asyncio
import getpass
import json
import os
import random
import socket
import subprocess
import threading
import time
import uuid

import pkgpanda.util
import pytest

from ssh.ssh_runner import MultiRunner
from ssh.utils import CommandChain

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
    runner = MultiRunner(['127.0.0.1:{}'.format(port) for port in sshd_ports], ssh_user=getpass.getuser(),
                         ssh_key_path=workspace + '/host_key')
    host_port = ['127.0.0.1:{}'.format(port) for port in sshd_ports]

    chain = CommandChain('test')
    chain.add_execute(['uname', '-a'])
    try:
        results = loop.run_until_complete(runner.run_commands_chain_async(chain, block=True))
    finally:
        loop.close()

    assert not os.path.isfile(workspace + '/test.json')
    assert len(results) == 20
    for host_result in results:
        for command_result in host_result:
            for host, process_result in command_result.items():
                assert process_result['returncode'] == 0, process_result['stderr']
                assert host in host_port
                assert '/usr/bin/ssh' in process_result['cmd']
                assert 'uname' in process_result['cmd']
                assert '-tt' in process_result['cmd']
                assert len(process_result['cmd']) == 13


def test_scp_remote_to_local(tmpdir, loop):
    workspace = tmpdir.strpath
    generate_fixtures(workspace)
    sshd_ports = start_random_sshd_servers(1, workspace)

    # wait a little bit for sshd server to start
    time.sleep(1)

    id = uuid.uuid4().hex
    pkgpanda.util.write_string(workspace + '/pilot.txt', id)
    runner = MultiRunner(['127.0.0.1:{}'.format(port) for port in sshd_ports], ssh_user=getpass.getuser(),
                         ssh_key_path=workspace + '/host_key')
    host_port = ['127.0.0.1:{}'.format(port) for port in sshd_ports]

    chain = CommandChain('test')
    chain.add_copy(workspace + '/pilot.txt.copied', workspace + '/pilot.txt', remote_to_local=True)
    try:
        copy_results = loop.run_until_complete(runner.run_commands_chain_async(chain, block=True,
                                                                               state_json_dir=workspace))
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
                assert '-tt' not in process_result['cmd']


def test_scp(tmpdir, loop):
    workspace = tmpdir.strpath
    generate_fixtures(workspace)
    sshd_ports = start_random_sshd_servers(1, workspace)

    # wait a little bit for sshd server to start
    time.sleep(1)

    id = uuid.uuid4().hex
    pkgpanda.util.write_string(workspace + '/pilot.txt', id)
    runner = MultiRunner(['127.0.0.1:{}'.format(port) for port in sshd_ports], ssh_user=getpass.getuser(),
                         ssh_key_path=workspace + '/host_key')
    host_port = ['127.0.0.1:{}'.format(port) for port in sshd_ports]

    chain = CommandChain('test')
    chain.add_copy(workspace + '/pilot.txt', workspace + '/pilot.txt.copied')
    try:
        copy_results = loop.run_until_complete(runner.run_commands_chain_async(chain, block=True,
                                                                               state_json_dir=workspace))
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
    runner = MultiRunner(['127.0.0.1:{}'.format(port) for port in sshd_ports], ssh_user=getpass.getuser(),
                         ssh_key_path=workspace + '/host_key')
    host_port = ['127.0.0.1:{}'.format(port) for port in sshd_ports]

    chain = CommandChain('test')
    chain.add_copy(workspace + '/recursive_pilot.txt', workspace + '/recursive_pilot.txt.copied', recursive=True)
    try:
        copy_results = loop.run_until_complete(runner.run_commands_chain_async(chain, block=True,
                                                                               state_json_dir=workspace))
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


def test_command_chain():
    chain = CommandChain('test')
    chain.add_execute(['cmd2'])
    chain.add_copy('/local', '/remote')
    chain.prepend_command(['cmd1'])
    chain.add_execute(['cmd3'])

    assert chain.get_commands() == [
        ('execute', ['cmd1'], None, None),
        ('execute', ['cmd2'], None, None),
        ('copy', '/local', '/remote', False, False, None),
        ('execute', ['cmd3'], None, None)
    ]


def test_ssh_command_terminate(tmpdir, loop):
    workspace = tmpdir.strpath
    generate_fixtures(workspace)
    sshd_ports = start_random_sshd_servers(1, workspace)

    # wait a little bit for sshd server to start
    time.sleep(3)

    runner = MultiRunner(['127.0.0.1:{}'.format(port) for port in sshd_ports], ssh_user=getpass.getuser(),
                         ssh_key_path=workspace + '/host_key', process_timeout=2)

    chain = CommandChain('test')
    chain.add_execute(['sleep', '20'])
    start_time = time.time()
    try:
        results = loop.run_until_complete(runner.run_commands_chain_async(chain, block=True, state_json_dir=workspace))
    finally:
        loop.close()
    elapsed_time = time.time() - start_time
    assert elapsed_time < 5
    assert os.path.isfile(workspace + '/test.json')

    with open(workspace + '/test.json') as fh:
        result_json = json.load(fh)
        assert result_json['total_hosts'] == 1
        assert result_json['hosts_terminated'] == 1
        assert 'hosts_failed' not in result_json
        assert 'hosts_success' not in result_json

    for host_result in results:
        for command_result in host_result:
            for host, process_result in command_result.items():
                assert process_result['stdout'] == ['']
                assert process_result['stderr'] == ['']
                assert process_result['returncode'] is None


def test_tags(tmpdir, loop):
    workspace = tmpdir.strpath
    generate_fixtures(workspace)
    sshd_ports = start_random_sshd_servers(1, workspace)
    host_ports = ['127.0.0.1:{}'.format(port) for port in sshd_ports]
    # wait a little bit for sshd server to start
    time.sleep(3)

    runner = MultiRunner(['127.0.0.1:{}'.format(port) for port in sshd_ports], ssh_user=getpass.getuser(),
                         ssh_key_path=workspace + '/host_key', tags=[{'tag1': 'test1'}, {'tag2': 'test2'}])

    chain = CommandChain('test')
    chain.add_execute(['sleep', '1'])
    try:
        loop.run_until_complete(runner.run_commands_chain_async(chain, block=True, state_json_dir=workspace))
    finally:
        loop.close()

    with open(workspace + '/test.json') as fh:
        result_json = json.load(fh)
        for host_port in host_ports:
            assert 'tags' in result_json['hosts'][host_port]
            assert len(result_json['hosts'][host_port]['tags']) == 2
            assert result_json['hosts'][host_port]['tags']['tag1'] == 'test1'
            assert result_json['hosts'][host_port]['tags']['tag2'] == 'test2'
            assert result_json['hosts'][host_port]['commands'][0]['cmd'] == [
                "/usr/bin/ssh",
                "-oConnectTimeout=10",
                "-oStrictHostKeyChecking=no",
                "-oUserKnownHostsFile=/dev/null",
                "-oBatchMode=yes",
                "-oPasswordAuthentication=no",
                "-p{}".format(sshd_ports[0]),
                "-i",
                "{}/host_key".format(workspace),
                "-tt",
                "{}@127.0.0.1".format(getpass.getuser()),
                "sleep",
                "1"
            ]
