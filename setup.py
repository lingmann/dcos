from setuptools import setup, find_packages
from codecs import open
from os import path

setup(
    name='dcos-pkg',
    version=0.1,
    description='DCOS blobg management + swapping',
    url='https://github.com/mesosphere/dcos-pkg',
    author='Mesosphere, Inc.',
    author_email='support@mesosphere.io',
    license='TODO',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: TODO License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
    ],

    packages=find_packages(exclude=['tests']),
    install_requires=['docopt'],
    entry_points={
        'console_scripts': [
            'dcos-pkg=package.cli:main',
        ],
    },
)