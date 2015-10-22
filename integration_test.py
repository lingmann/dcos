import json
import os
import pytest
import requests
import uuid
import time


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

    def post(self, path="", payload=None):
        if payload is None:
            payload = {}
        return requests.post(self.uri + path, json=payload)

    def delete(self, path=""):
        return requests.delete(self.uri + path)


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
    r = cluster.get('exhibitor/exhibitor/v1/cluster/status')
    assert r.status_code == 200


def test_MarathonAppWorking(cluster):
    rnd = uuid.uuid4().hex
    app = '/integrationtest-{}'.format(rnd)

    payload = {
        'id': app,
        'container': {
            'type': 'DOCKER',
            'docker': {
                'image': 'nginx',
                'network': 'BRIDGE',
                'portMappings': [
                    {'containerPort':  80, 'hostPort': 0, 'servicePort': 0, 'protocol': 'tcp'}
                ]
            }
        },
        'cpus': 0.01,
        'mem': 64,
        'instances': 1,
        'ports': [0],
        'healthChecks':
        [
            {
                'protocol': 'HTTP',
                'path': '/',
                'portIndex': 0,
                'gracePeriodSeconds': 5,
                'intervalSeconds': 10,
                'timeoutSeconds': 10,
                'maxConsecutiveFailures': 3
            }
        ]
    }

    # create app
    r = cluster.post('marathon/v2/apps', payload)
    assert r.ok

    # wait for app to run
    tasksRunning = 0
    tasksHealthy = 0

    timeout = time.time() + 300
    while tasksRunning != 1 or tasksHealthy != 1:
        r = cluster.get('marathon/v2/apps' + app)
        if r.ok:
            json = r.json()
            print('fetched app status {}'.format(json))
            tasksRunning = json['app']['tasksRunning']
            tasksHealthy = json['app']['tasksHealthy']

            if tasksHealthy == 1:
                remote_host = json['app']['tasks'][0]['host']
                remote_port = json['app']['tasks'][0]['ports'][0]
                print('running on {}:{} with {}/{} healthy tasks'.format(
                    remote_host, remote_port, tasksHealthy, tasksRunning))
                break

        if time.time() > timeout:
            print('timeout while waiting for healthy task')
            break

        time.sleep(5)

    assert tasksRunning == 1
    assert tasksHealthy == 1

    # fetch test file from launched app
    r = requests.get('http://{}:{}/'.format(remote_host, str(remote_port)))
    assert r.ok

    # delete app
    r = cluster.delete('marathon/v2/apps' + app)
    assert r.ok
