#!/usr/bin/python
import json
import os
import requests
import subprocess
import sys
import unittest

from DCOSCluster import DCOSCluster


DCOS_CLI_URI = 'https://raw.githubusercontent.com/mesosphere/install-scripts/master/dcos-cli/install-dcos-cli-ea2.sh'


class DCOSTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        region = os.getenv('AWS_REGION')
        aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
        aws_secret_key = os.getenv('AWS_SECRET_KEY')

        stack_name = os.getenv('DCOS_STACK_NAME')
        dcos = DCOSCluster(region=region,
                           aws_access_key_id=aws_access_key_id,
                           aws_secret_key=aws_secret_key,
                           stack_name=stack_name,
                           params={}
                           )
        self.dcos = dcos

        self.install_cli(self.dcos.dns_name)

    @classmethod
    def install_cli(cls, hostname):
        subprocess.call(['pyvenv', 'test-venv'])
        subprocess.call(['curl', '-o', 'test-venv/install-dcos-cli-ea2.sh', DCOS_CLI_URI])
        subprocess.call(['bash', 'test-venv/install-dcos-cli-ea2.sh', 'test-venv', hostname])
        subprocess.call(['test-venv/bin/dcos', 'config', 'show'])

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
        stdout, stderr = subprocess.Popen(
            ['dcos', 'package', 'list-installed'],
            stdout=subprocess.PIPE).communicate()
        self.assertIsNotNone(stdout)

        output = json.loads(stdout)

        package_list = [x for x in output if (x.get('appId')) == package_name]

        self.assertEquals(1, len(package_list))

    def assertStatusRunning(self, app):
        stdout, stderr = subprocess.Popen([
            'dcos', 'marathon', 'app', 'show', app],
            stdout=subprocess.PIPE).communicate()

        self.assertIsNotNone(stdout)
        j = json.loads(stdout)

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
        subprocess.call(['dcos', 'package', 'install', 'spark'])

        self.assertPackageInstalled(app)
        self.assertStatusRunning(app)

        # submit spark job
        stdout, stderr = subprocess.Popen(['dcos', 'spark', 'run', '--submit-args=-Dspark.mesos.coarse=true --driver-cores 1 --driver-memory 1024M --class org.apache.spark.examples.SparkPi http://downloads.mesosphere.com.s3.amazonaws.com/assets/spark/spark-examples_2.10-1.4.0-SNAPSHOT.jar 30'],
                stdout=subprocess.PIPE).communicate()

        # assert something more here
        self.assertIsNotNone(stdout)

        self.assertTaskWebPortsUp(app)

    def testCassandraInstall(self):
        app = '/cassandra/dcos'
        subprocess.call(['dcos', 'package', 'install', 'cassandra'])

        self.assertPackageInstalled(app)
        self.assertStatusRunning(app)
        self.assertTaskWebPortsUp(app)

    def testChronosInstall(self):
        app = '/chronos'
        subprocess.call(['dcos', 'package', 'install', 'chronos'])

        self.assertPackageInstalled(app)
        self.assertStatusRunning(app)
        self.assertTaskWebPortsUp(app)

    @classmethod
    def tearDownClass(self):
        # self.dcos.delete()
        pass


if __name__ == '__main__':
    unittest.main(verbosity=2)
