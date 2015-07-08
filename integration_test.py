import json
import os
import pytest
import requests


def assertTaskWebPortsUp(cluster, app):
    # app must begin with trailing '/'
    assert app.startswith('/')
    r = requests.get("%s/marathon/v2/apps%s" % (cluster.uri, app))
    j = r.json()
    tasks = j.get('app').get('tasks')

    for task in tasks:
        host = task.get('host')
        ports = task.get('ports')

        for port in ports:
            r = requests.get("http://%s:%s" % (host, port))
            # basically just check if it's serving
            assert r.status_code != 500


def assertPackageInstalled(cluster, package_name):
    stdout, stderr = cluster.cli(['package', 'list-installed'])
    assert stdout is not None

    output = json.loads(stdout.decode())

    package_list = [x for x in output if (x.get('appId')) == package_name]

    assert len(package_list) == 1


def assertStatusRunning(cluster, app):
    stdout, stderr = cluster.cli(['marathon', 'app', 'show', app])

    assert stdout is not None
    j = json.loads(stdout.decode())

    assert j.get('tasksHealthy') > 0
    assert j.get('tasksRunning') > 0
    assert j.get('tasksStaged') == 0
    assert j.get('tasksUnhealthy') == 0


@pytest.fixture(scope='module')
def cluster():
    # Must set the cluster DNS address as an environment parameter
    assert 'DCOS_DNS_ADDRESS' in os.environ

    return Cluster(os.environ['DCOS_DNS_ADDRESS'])


class Cluster:

    def __init__(self, uri):
        # URI must include scheme
        assert uri.startswith('http')

        # Make URI always end with '/'
        if uri[-1] != '/':
            uri += '/'

        self.uri = uri

    def get(self, path=""):
        return requests.get(self.uri + path)


def test_DCOSUIUp(cluster):
    r = cluster.get('/')
    assert r.status_code == 200


def test_MarathonUp(cluster):
    r = cluster.get('marathon')
    assert r.status_code == 200


def test_MesosUp(cluster):
    # TODO(cmaloney): Test number of slaves registered, public_slaves registered
    # As well as number of masters. This doesn't provide much as the ui being up
    # means the leading mesos master is up
    r = cluster.get('mesos')
    assert r.status_code == 200


def test_ExhibitorUp(cluster):
    r = cluster.get("exhibitor/exhibitor/v1/cluster/status")
    assert r.status_code == 200
