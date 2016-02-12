#!/usr/bin/env python3
import os
import subprocess

import setuptools
from setuptools import find_packages, setup


class BuildUi(setuptools.Command):
    description = 'Use system docker and public npm image to build UI'
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        src_dir = os.path.dirname(os.path.abspath(__file__))
        cmd = ['docker', 'run', '-v', "{}:/code".format(src_dir),
                '-w', '/code/ui', 'node:4.2.6', 'npm', 'install']
        subprocess.check_call(cmd)
        cmd = ['docker', 'run', '-v', "{}:/code".format(src_dir),
                '-w', '/code/ui', 'node:4.2.6', './node_modules/.bin/gulp', 'dist']
        subprocess.check_call(cmd)

setup(
    name='dcos_installer',
    description='The DCOS Installer',
    version='0.1',
    author='Mesosphere, Inc.',
    author_email='support@mesosphere.io',
    cmdclass={
        'build_ui': BuildUi},
    packages=['dcos_installer'] + find_packages(),
    install_requires=[
        'asyncio',
        'aiohttp==0.20.0',
        'aiohttp_jinja2',
        'coloredlogs',
        'docker_py',
        'passlib',
        'pytest',
        'pytest-mock',
        'pyyaml',
        'webtest',
        'webtest_aiohttp==1.0.0'],
    entry_points={
        'console_scripts': [
            'dcos_installer = dcos_installer.entrypoint:main']
        },
    include_package_data=True,
    zip_safe=False
    )
