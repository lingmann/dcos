import bs4
import dns.exception
import dns.resolver
import json
import kazoo.client
import logging
import os
import pytest
import requests
import retrying
import time
import urllib.parse
import uuid


ZK_HOSTS = os.environ.get('ZK_HOSTS', '127.0.0.1:2181')
ZK_IPS = set(hostport.split(':')[0] for hostport in ZK_HOSTS.split(','))
LOG_LEVEL = logging.INFO


@pytest.fixture(scope='module')
def cluster():
    # Must set the cluster DNS address as an environment parameter
    assert 'DCOS_DNS_ADDRESS' in os.environ

    _setup_logging()

    return Cluster(os.environ['DCOS_DNS_ADDRESS'])


def _setup_logging():
    """Setup logging for the script"""
    logger = logging.getLogger()
    logger.setLevel(LOG_LEVEL)
    fmt = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
    handler = logging.StreamHandler()
    handler.setFormatter(fmt)
    logger.addHandler(handler)

    logging.getLogger("requests").setLevel(logging.WARNING)


class Cluster:
    @retrying.retry(wait_fixed=1000,
                    retry_on_result=lambda ret: ret is False,
                    retry_on_exception=lambda x: False)
    def _wait_for_Marathon_up(self):
        r = self.get('marathon/ui/')
        # resp_code >= 500 -> backend is still down probably
        if r.status_code < 500:
            logging.info("Marathon is probably up")
            return True
        else:
            msg = "Waiting for Marathon, resp code is: {}"
            logging.info(msg.format(r.status_code))
            return False

    @retrying.retry(wait_fixed=1000,
                    retry_on_result=lambda ret: ret is False,
                    retry_on_exception=lambda x: False)
    def _wait_for_slaves_to_join(self):
        r = self.get('mesos/master/slaves')
        if r.status_code != 200:
            msg = "Mesos master returned status code {} != 200 "
            msg += "continuing to wait..."
            logging.info(msg.format(r.status_code))
            return False
        data = r.json()
        num_slaves = len([x['hostname'] for x in data['slaves']])
        if num_slaves >= 2:
            msg = "Sufficient ({} >= 2) number of slaves have joined the cluster"
            logging.info(msg.format(num_slaves))
            return True
        else:
            msg = "Curent number of slaves: {}, continuing to wait..."
            logging.info(msg.format(num_slaves))
            return False

    @retrying.retry(wait_fixed=1000,
                    retry_on_result=lambda ret: ret is False,
                    retry_on_exception=lambda x: False)
    def _wait_for_DCOS_history_up(self):
        r = self.get('dcos-history-service/ping')
        # resp_code >= 500 -> backend is still down probably
        if r.status_code <= 500:
            logging.info("DCOS History is probably up")
            return True
        else:
            msg = "Waiting for DCOS History, resp code is: {}"
            logging.info(msg.format(r.status_code))
            return False

    @retrying.retry(wait_fixed=1000,
                    retry_on_result=lambda ret: ret is False,
                    retry_on_exception=lambda x: False)
    def _wait_for_leader_election(self):
        mesos_resolver = dns.resolver.Resolver()
        mesos_resolver.nameservers = list(ZK_IPS)
        try:
            # Yeah, we can also put it in retry_on_exception, but
            # this way we will loose debug messages
            mesos_resolver.query('leader.mesos', 'A')
        except dns.exception.DNSException as e:
            msg = "Cannot resolve leader.mesos, error string: '{}', continuing to wait"
            logging.info(msg.format(e))
            return False
        else:
            logging.info("leader.mesos dns entry is UP!")
            return True

    @retrying.retry(wait_fixed=1000,
                    retry_on_result=lambda ret: ret is False,
                    retry_on_exception=lambda x: False)
    def _wait_for_nginx_up(self):
        try:
            # Yeah, we can also put it in retry_on_exception, but
            # this way we will loose debug messages
            self.get()
        except requests.ConnectionError as e:
            msg = "Cannot connect to nginx, error string: '{}', continuing to wait"
            logging.info(msg.format(e))
            return False
        else:
            logging.info("Nginx is UP!")
            return True

    def _wait_for_DCOS(self):
        self._wait_for_leader_election()
        self._wait_for_nginx_up()
        self._wait_for_Marathon_up()
        self._wait_for_slaves_to_join()
        self._wait_for_DCOS_history_up()

    def __init__(self, uri):
        # URI must include scheme
        assert uri.startswith('http')

        # Make URI always end with '/'
        if uri[-1] != '/':
            uri += '/'
        self.uri = uri

        self._wait_for_DCOS()

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


def test_if_all_Mesos_slaves_have_registered(cluster):
    r = cluster.get('mesos/master/slaves')
    assert r.status_code == 200

    data = r.json()
    slaves_ips = sorted(x['hostname'] for x in data['slaves'])

    assert len(data['slaves']) == 2
    assert slaves_ips == ['172.17.10.201', '172.17.10.202']


def test_if_srouter_slaves_endpoint_work(cluster):
    r = cluster.get('mesos/master/slaves')
    assert r.status_code == 200

    data = r.json()
    slaves_ids = sorted(x['id'] for x in data['slaves'])

    for slave_id in slaves_ids:
        uri = 'slave/{}/slave%281%29/state.json'.format(slave_id)
        r = cluster.get(uri)
        assert r.status_code == 200

        data = r.json()
        assert "id" in data
        assert data["id"] == slave_id


def test_if_all_Mesos_masters_have_registered(cluster):
    # Currently it is not possible to extract this information through Mesos'es
    # API, let's query zookeeper directly.
    zk = kazoo.client.KazooClient(hosts=ZK_HOSTS, read_only=True)
    master_ips = set()

    zk.start()
    for znode in zk.get_children("/mesos"):
        if not znode.startswith("json.info_"):
            continue
        master = json.loads(zk.get("/mesos/" + znode)[0].decode('utf-8'))
        master_ips.add(master['address']['ip'])
    zk.stop()

    assert master_ips == ZK_IPS


def test_if_Exhibitor_API_is_up(cluster):
    r = cluster.get('exhibitor/exhibitor/v1/cluster/list')
    assert r.status_code == 200

    data = r.json()
    assert data["port"] > 0


def test_if_Exhibitor_UI_is_up(cluster):
    r = cluster.get('exhibitor')
    assert r.status_code == 200
    assert 'Exhibitor for ZooKeeper' in r.text


def test_if_ZooKeeper_cluster_is_up(cluster):
    r = cluster.get('exhibitor/exhibitor/v1/cluster/status')
    assert r.status_code == 200

    data = r.json()
    serving_zks = sum(1 for x in data if x['code'] == 3)
    zks_ips = set(x['hostname'] for x in data)
    zks_leaders = sum(1 for x in data if x['isLeader'])

    assert serving_zks == len(ZK_IPS)
    assert zks_leaders == 1
    assert zks_ips == ZK_IPS


def test_if_all_exhibitors_are_in_sync(cluster):
    r = cluster.get('exhibitor/exhibitor/v1/cluster/status')
    assert r.status_code == 200

    correct_data = sorted(r.json(), key=lambda k: k['hostname'])

    for zk_ip in ZK_IPS:
        resp = requests.get('http://{}:8181/exhibitor/v1/cluster/status'.format(zk_ip))
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


def test_if_srouter_service_endpoint_works(cluster):
    r = cluster.get('service/marathon/ui/')

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
            logging.debug('fetched app status {}'.format(json))
            tasksRunning = json['app']['tasksRunning']
            tasksHealthy = json['app']['tasksHealthy']

            if tasksHealthy == 1:
                remote_host = json['app']['tasks'][0]['host']
                remote_port = json['app']['tasks'][0]['ports'][0]
                logging.info('running on {}:{} with {}/{} healthy tasks'.format(
                    remote_host, remote_port, tasksHealthy, tasksRunning))
                break

        if time.time() > timeout:
            logging.warn('timeout while waiting for healthy task')
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
