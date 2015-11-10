import bs4
import json
import kazoo.client
import os
import pytest
import requests
import time
import urllib.parse
import uuid


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

    def head(self, path=""):
        return requests.head(self.uri + path)


def test_if_DCOS_UI_is_up(cluster):
    r = cluster.get('/')

    assert r.status_code == 200
    assert len(r.text) > 100
    assert 'Mesosphere DCOS' in r.text

    # Not sure if it's really needed, seems a bit of an overkill:
    soup = bs4.BeautifulSoup(r.text, "html.parser")
    for link in soup.find_all(['link', 'a'], href=True):
        if urllib.parse.urlparse(link.attrs['href']).netloc:
            # Relative URLs only, others are to complex to handle here
            continue
        link_response = cluster.head(link.attrs['href'])
        assert link_response.status_code == 200


def test_if_Mesos_is_up(cluster):
    r = cluster.get('mesos')

    assert r.status_code == 200
    assert len(r.text) > 100
    assert '<title>Mesos</title>' in r.text


# FIXME: DCOS-3496
# TLDR: there is a problem with Mesos on agent4-1. Even though the leader was
# elected, slaves are not joining and the test is failing. Work is in progress
# with developers on debugging it.
# def test_if_all_Mesos_slaves_have_registered(cluster):
    # r = cluster.get('mesos/master/slaves')
    # data = r.json()
    # slaves_ips = sorted(x['hostname'] for x in data['slaves'])

    # assert r.status_code == 200
    # assert len(data['slaves']) == 2
    # assert slaves_ips == ['172.17.10.201', '172.17.10.202']


def test_if_all_Mesos_masters_have_registered(cluster):
    # Currently it is not possible to extract this information through Mesos'es
    # API, let's query zookeeper directly.
    zk = kazoo.client.KazooClient(hosts="172.17.10.101:2181,"
                                        "172.17.10.102:2181,"
                                        "172.17.10.103:2181",
                                  read_only=True)
    masters = []
    zk.start()
    for znode in zk.get_children("/mesos"):
        if not znode.startswith("json.info_"):
            continue
        tmp = zk.get("/mesos/" + znode)[0].decode('utf-8')
        masters.append(json.loads(tmp))
    zk.stop()
    masters_ips = sorted(x['address']['ip'] for x in masters)

    assert len(masters) == 3
    assert masters_ips == ['172.17.10.101', '172.17.10.102', '172.17.10.103']


def test_if_Exhibitor_is_up(cluster):
    r = cluster.get('exhibitor/exhibitor/v1/cluster/list')
    assert r.status_code == 200

    data = r.json()
    assert data["port"] > 0


def test_if_ZooKeeper_cluster_is_up(cluster):
    r = cluster.get('exhibitor/exhibitor/v1/cluster/status')
    assert r.status_code == 200

    data = r.json()
    serving_zks = sum(1 for x in data if x['code'] == 3)
    zks_ips = sorted(x['hostname'] for x in data)
    zks_leaders = sum(1 for x in data if x['isLeader'])

    assert serving_zks == 3
    assert zks_leaders == 1
    assert zks_ips == ['172.17.10.101', '172.17.10.102', '172.17.10.103']


def test_if_all_exhibitors_are_in_sync(cluster):
    r = cluster.get('exhibitor/exhibitor/v1/cluster/status')
    assert r.status_code == 200

    correct_data = sorted(r.json(), key=lambda k: k['hostname'])

    for ex in ['172.17.10.101', '172.17.10.102', '172.17.10.103']:
        resp = requests.get('http://{}:8181/exhibitor/v1/cluster/status'.format(ex))
        assert resp.status_code == 200

        tested_data = sorted(resp.json(), key=lambda k: k['hostname'])
        assert correct_data == tested_data


def test_if_DCOSHistoryService_is_up(cluster):
    r = cluster.get('dcos-history-service/ping')

    assert r.status_code == 200
    assert 'pong' == r.text


def test_if_Marathon_UI_is_up(cluster):
    r = cluster.get('marathon/ui/')

    assert r.status_code == 200
    assert len(r.text) > 100
    assert '<title>Marathon</title>' in r.text


def test_if_Mesos_API_is_up(cluster):
    r = cluster.get('mesos_dns/v1/version')
    assert r.status_code == 200

    data = r.json()
    assert data["Service"] == 'Mesos-DNS'


def test_if_PkgPanda_metadata_is_available(cluster):
    r = cluster.get('pkgpanda/active.buildinfo.full.json')
    assert r.status_code == 200

    data = r.json()
    assert 'mesos' in data
    assert len(data) > 5  # (prozlach) We can try to put minimal number of pacakages required


def test_if_Marathon_app_can_be_deployed(cluster):
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


def test_if_DCOSHistoryService_is_getting_data(cluster):
    r = cluster.get('dcos-history-service/history/last')
    assert r.status_code == 200
    # Make sure some basic fields are present from state-summary which the DCOS
    # UI relies upon. Their exact content could vary so don't test the value.
    json = r.json()
    assert 'cluster' in json
    assert 'frameworks' in json
    assert 'slaves' in json
    assert 'hostname' in json
