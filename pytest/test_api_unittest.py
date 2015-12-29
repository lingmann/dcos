import json
import unittest
import unittest.mock
import yaml

from installer.api import app


api_version = 'v1'


class TestApi(unittest.TestCase):
    def setUp(self):
        pass

    def test_root_redirect(self):
        tester = app.test_client(self)
        response = tester.get('/')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers['location'], 'http://localhost/api/{}'.format(api_version))

    def test_base_route(self):
        tester = app.test_client(self)
        response = tester.get('/api/{}'.format(api_version))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Content-Type'], 'text/html; charset=utf-8')
        self.assertRegex(response.data, b'<!DOCTYPE html>', msg='Detected HTML document')

    def test_configure_route(self):
        """
        Today, we're using a mock validator on the backend. This test assumes the GET
        request will return the mock data in mock.py, and on POST the DCOSConfig class
        will override the data in mock with the variables in the POST. This will likely
        have to be updated after the real backend code is pushed out, however, the
        general testing method around GET and POST should still be the same.
        """
        # We should probably use JSON here, but I lazily copied this from
        # our base default config.
        mock_get_resp = """
---
cluster_config:
  bootstrap_url: file:///opt/dcos_install_tmp
  cluster_name: 'Mesosphere: The Data Center Operating System'
  docker_remove_delay: 1hrs
  exhibitor_storage_backend: zookeeper
  exhibitor_zk_hosts: 127.0.0.1:2181
  exhibitor_zk_path: /exhibitor
  gc_delay: 2days
  ip_detect_path: /genconf/ip-detect
  master_discovery: static
  master_list: null
  num_masters: null
  resolvers:
  - 8.8.8.8
  - 8.8.4.4
  roles: slave_public
  weights: slave_public=1
ssh_config:
  log_directory: /genconf/logs
  ssh_key_path: /genconf/ssh_key
  ssh_port: 22
  ssh_user: Null
  target_hosts:
  - null
"""

        mock_config_post = json.dumps({
            "ssh_config": {
                "ssh_user": "testcase"}})

        mock_post_resp = """
{
  "cluster_config": {
    "ip_detect_path": "/genconf/ip-detect",
    "num_masters": null,
    "gc_delay": "2days",
    "roles": "slave_public",
    "master_list": null,
    "docker_remove_delay": "1hrs",
    "weights": "slave_public=1",
    "master_discovery": "static",
    "exhibitor_storage_backend": "zookeeper",
    "cluster_name": "Mesosphere: The Data Center Operating System",
    "exhibitor_zk_path": "/exhibitor",
    "bootstrap_url": "file:///opt/dcos_install_tmp",
    "exhibitor_zk_hosts": "127.0.0.1:2181",
    "resolvers": [
      "8.8.8.8",
      "8.8.4.4"
    ]
  },
  "ssh_config": {
    "ssh_port": 22,
    "ssh_key_path": "/genconf/ssh_key",
    "target_hosts": [
      null
    ],
    "ssh_user": "testcase",
    "log_directory": "/genconf/logs"
  }
}
"""

        tester = app.test_client(self)
        # Test the GET method
        get_response = tester.get('/api/{}/configure'.format(api_version), content_type='application/json')
        self.assertEqual(get_response.status_code, 200)
        # Test the header since this needs to be applciation/json for the json loader in flask to work
        self.assertEqual(get_response.headers['Content-Type'], 'application/json')
        # Test that mock data returned is in fact the data expected.
        self.assertEqual(json.loads(get_response.data.decode("utf-8")), yaml.load(mock_get_resp))
        # Test the POST method
        post_response = tester.post(
            '/api/{}/configure'.format(api_version),
            content_type='application/json',
            data=mock_config_post)
        self.assertEqual(post_response.status_code, 200)
        self.assertEqual(json.loads(post_response.data.decode("utf-8")), json.loads(mock_post_resp))
        # Test 405
        method_not_allowed_response = tester.put(
            '/api/{}/configure'.format(api_version),
            content_type='application/json',
            data='{"foo": "bar"}')
        self.assertEqual(method_not_allowed_response.status_code, 405)
        # Test 400 - current mock validation will return 200 on this, but shouldn't.
        # bad_request_response = tester.post(
        #    '/api/{}/configure'.format(api_version),
        #    content_type='application/json',
        #    data='{"foo": "bar"}')
        # self.assertEqual(bad_request_response.status_code, 400)

    def test_action_name_route(self):
        mock_action_state_resp = {
            "10.0.0.1": {
                "role": "master",
                "state": "not_running",
                "cmd": "",
                "returncode": -1,
                "stderr": [""],
                "stdout": [""]
            },
            "10.0.0.2": {
                "role": "slave",
                "state": "running",
                "cmd": "",
                "returncode": -1,
                "stderr": [""],
                "stdout": [""]
            },
            "10.0.0.3": {
                "role": "slave",
                "state": "not_running",
                "cmd": "",
                "returncode": -1,
                "stderr": [""],
                "stdout": [""]
            },
            "10.0.0.4": {
                "role": "slave",
                "state": "success",
                "cmd": "",
                "returncode": -1,
                "stderr": [""],
                "stdout": [""]
            },
            "10.0.0.5": {
                "role": "slave",
                "state": "error",
                "cmd": "",
                "returncode": -1,
                "stderr": [""],
                "stdout": [""]
            }
        }
        # Test GET for each good route
        good_actions = ['deploy', 'postflight', 'preflight']
        tester = app.test_client(self)
        for action in good_actions:
            get_response = tester.get(
                '/api/{}/{}'.format(api_version, action))
            self.assertEqual(get_response.status_code, 200)
            self.assertEqual(json.loads(get_response.data.decode("utf-8")), mock_action_state_resp)
        # Test repudiation of none-actions
        get_response = tester.get('/api/{}/foo'.format(api_version))
        self.assertEqual(get_response.status_code, 404)
        # Test POST

    def test_success_route(self):
        mock_success_resp = '{"dcosUrl": "http://foobar.com"}'
        tester = app.test_client(self)
        get_response = tester.get(
            '/api/{}/success'.format(api_version))
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(json.loads(get_response.data.decode("utf-8")), json.loads(mock_success_resp))
        # Test none-GET
        not_allowed = ['tester.post', 'tester.put', 'tester.delete']
        for method in not_allowed:
            method_disallowed_response = getattr(not_allowed, method)(
                '/api/{}/success'.format(api_version))
            self.assertEqual(method_disallowed_response, 405)

    
