from setuptools import setup, find_packages
from setuptools.command.test import test as TestCommand
import sys

setup(
    name='dcos_installer',
    description='The DCOS Installer',
    author='Mesosphere, Inc.',
    author_email='support@mesosphere.io',
    packages=['dcos_installer'] + find_packages(),
    install_requires=[
        'asyncio',
        'aiohttp',
        'aiohttp_jinja2',
        'pytest',
        'tox',
        'webtest_aiohttp'],
    entry_points={
        'console_scripts': ['dcos_installer = dcos_installer.entrypoint:main']
        },
    package_data={
        'dcos_installer': [
            'templates/*',
        ]
    })
