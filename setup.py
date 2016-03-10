#!/usr/bin/env python3
import os
import subprocess

from setuptools import Command, find_packages, setup
from setuptools.command.test import test as TestCommand


class PyTest(TestCommand):
    user_options = [('pytest-args=', 'a', "Arguments to pass to py.test")]

    def initialize_options(self):
        TestCommand.initialize_options(self)
        self.pytest_args = ""

    def run_tests(self):
        # import here so that pytest is not included in packaing
        import pytest
        # name pytest dir so that irrelevent dirs are not tested
        errno = pytest.main(str(self.pytest_args)+" pytest/")
        exit(errno)


class BuildUi(Command):
    description = 'Use system docker and public npm image to build UI'
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        src_dir = os.path.dirname(os.path.abspath(__file__))
        cmd = [
            'docker', 'run', '-v', "{}:/code".format(src_dir),
            '-w', '/code/ui', 'node:4.2.6', 'npm', 'install']
        subprocess.check_call(cmd)
        cmd = [
            'docker', 'run', '-v', "{}:/code".format(src_dir),
            '-w', '/code/ui', 'node:4.2.6', './node_modules/.bin/gulp', 'dist']
        subprocess.check_call(cmd)


setup(
    name='dcos_installer',
    description='The DCOS Installer',
    version='0.1',
    author='Mesosphere, Inc.',
    author_email='support@mesosphere.io',
    cmdclass={
        'test': PyTest,
        'build_ui': BuildUi},
    packages=['dcos_installer'] + find_packages(),
    install_requires=[
        'aiohttp==0.20.0',
        'aiohttp_jinja2',
        'coloredlogs',
        'passlib',
        'pyyaml'],
    tests_require=[
        'pytest==2.9.0',
        'pytest-mock==0.11.0',
        'webtest==2.0.20',
        'webtest-aiohttp==1.0.0'],
    test_suite='pytest',
    entry_points={
        'console_scripts': [
            'dcos_installer = dcos_installer.entrypoint:main']
        },
    include_package_data=True,
    zip_safe=False
    )
