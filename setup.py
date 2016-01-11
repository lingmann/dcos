from setuptools import setup, find_packages
from setuptools.command.test import test as TestCommand
import sys

class Tox(TestCommand):
    user_options = [('tox-args=', 'a', "Arguments to pass to tox")]

    def initialize_options(self):
        TestCommand.initialize_options(self)
        self.tox_args = None

    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        import tox
        import shlex
        args = self.tox_args
        if args:
            args = shlex.split(self.tox_args)
        errno = tox.cmdline(args=args)
        sys.exit(errno)

setup(
    name='dcos_installer',
    description='The DCOS Installer',
    author='Mesosphere, Inc.',
    author_email='support@mesosphere.io',
    tests_require=['tox'],
    cmdclass={'test': Tox},
    packages=['dcos_installer'] + find_packages(),
    install_requires=[
        'asyncio',
        'aiohttp',
        'aiohttp_jinja2',
        'webtest_aiohttp',
        'pytest'],
    setup_requires=['pytest'],
    package_data={
        'dcos_installer': [
            'templates/*',
        ]
    })
