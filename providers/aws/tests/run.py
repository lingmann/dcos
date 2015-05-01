#!/usr/bin/env python3
"""
USAGE: run <dcos_name> [<cluster_name>]
"""
import docopt
import json
import os
import requests
import subprocess
import unittest

from boto.exception import BotoServerError
from DCOSCluster import DCOSCluster


DCOS_CLI_URI = 'https://raw.githubusercontent.com/mesosphere/install-scripts/master/dcos-cli/install-dcos-cli-ea2.sh'


class DCOSTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        region = os.getenv('AWS_REGION')
        aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
        aws_secret_key = os.getenv('AWS_SECRET_KEY')

        stack_name = os.getenv('DCOS_STACK_NAME')
        dcos_version = os.getenv('DCOS_VERSION')
        dcos = DCOSCluster(region=region,
                           aws_access_key_id=aws_access_key_id,
                           aws_secret_key=aws_secret_key,
                           stack_name=stack_name,
                           template_url=self.get_template_url(dcos_version),
                           params={'KeyName': 'default', 'AcceptEULA': 'Yes'})
        self.dcos = dcos

        try:
            self.dcos.create()
        except BotoServerError as e:
            if 'AlreadyExistsException' in e.body:
                print(e.body)
            else:
                raise e

        self.install_cli(self.dcos.dns_name)

    @classmethod
    def get_template_url(self, dcos_name):
        return "https://s3.amazonaws.com/downloads.mesosphere.io/dcos/testing/%s/single-master.cloudformation.json" %(dcos_name)


    @classmethod
    def install_cli(cls, hostname):
        venv = 'test-venv'
        subprocess.call(['pyvenv', venv])
        subprocess.call(['curl', '-o', '%s/install-dcos-cli-ea2.sh' % (venv), DCOS_CLI_URI])
        subprocess.call(['bash', '%s/install-dcos-cli-ea2.sh' % (venv), venv, hostname])
        subprocess.call(['%s/bin/dcos' % (venv), 'config', 'show'])

        cls.dcos_cli_root = venv

    def dcos_cli(self, commands=[]):
        return subprocess.Popen(["%s/bin/dcos" % (self.dcos_cli_root)] + commands,
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE).communicate()

    def assertTaskWebPortsUp(self, app):
        # app must begin with trailing '/'
        self.assertTrue(app.startswith('/'))
        r = requests.get("%s:8080/v2/apps%s" % (self.dcos.uri, app))
        j = r.json()
        tasks = j.get('app').get('tasks')

        for task in tasks:
            host = task.get('host')
            ports = task.get('ports')

            for port in ports:
                r = requests.get("http://%s:%s" % (host, port))
                # basically just check if it's serving
                self.assertNotEqual(r.status_code, 500)

    def assertPackageInstalled(self, package_name):
        stdout, stderr = self.dcos_cli(['package', 'list-installed'])
        self.assertIsNotNone(stdout)

        output = json.loads(stdout.decode())

        package_list = [x for x in output if (x.get('appId')) == package_name]

        self.assertEquals(1, len(package_list))

    def assertStatusRunning(self, app):
        stdout, stderr = self.dcos_cli(['marathon', 'app', 'show', app])

        self.assertIsNotNone(stdout)
        j = json.loads(stdout.decode())

        self.assertGreater(j.get('tasksHealthy'), 0)
        self.assertGreater(j.get('tasksRunning'), 0)
        self.assertEquals(0, j.get('tasksStaged'))
        self.assertEquals(0, j.get('tasksUnhealthy'))

    def testHasDNSName(self):
        self.assertIsNotNone(self.dcos.dns_name)

    def testDCOSUIUp(self):
        r = requests.get(self.dcos.uri)
        self.assertEqual(r.status_code, 200)

    def testMarathonUp(self):
        r = requests.get("%s:8080" % (self.dcos.uri))
        self.assertEqual(r.status_code, 200)

    def testMesosUp(self):
        r = requests.get("%s:5050" % (self.dcos.uri))
        self.assertEqual(r.status_code, 200)

    def testExhibitorUp(self):
        r = requests.get(
            "%s:8181/exhibitor/v1/cluster/status" % (self.dcos.uri))
        self.assertEqual(r.status_code, 200)

    def testSparkInstall(self):
        app = '/spark'
        self.dcos_cli(['package', 'install', 'spark'])

        self.assertPackageInstalled(app)
        self.assertStatusRunning(app)

        # submit spark job
        stdout, stderr = self.dcos_cli(['spark', 'run', '--submit-args=-Dspark.mesos.coarse=true --driver-cores 1 --driver-memory 1024M --class org.apache.spark.examples.SparkPi http://downloads.mesosphere.com.s3.amazonaws.com/assets/spark/spark-examples_2.10-1.4.0-SNAPSHOT.jar 30'])

        # assert something more here
        self.assertIsNotNone(stdout)

        self.assertTaskWebPortsUp(app)

    def testCassandraInstall(self):
        app = '/cassandra/dcos'
        self.dcos_cli(['package', 'install', 'cassandra'])

        self.assertPackageInstalled(app)
        self.assertStatusRunning(app)
        self.assertTaskWebPortsUp(app)

    def testChronosInstall(self):
        app = '/chronos'
        self.dcos_cli(['package', 'install', 'chronos'])

        self.assertPackageInstalled(app)
        self.assertStatusRunning(app)
        self.assertTaskWebPortsUp(app)

    @classmethod
    def tearDownClass(self):
        # self.dcos.delete()
        pass


if __name__ == '__main__':
    args = docopt.docopt(__doc__, version=0.1)
    # work on naming here
    os.environ['DCOS_STACK_NAME'] = args['<cluster_name>']
    os.environ['DCOS_VERSION'] = args['<dcos_name>']
    suite = unittest.TestLoader().loadTestsFromTestCase(DCOSTestCase)
    unittest.TextTestRunner(verbosity=2).run(suite)
