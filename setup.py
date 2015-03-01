from setuptools import setup, find_packages
from package.constants import version

setup(
    name='pkgpanda',
    version=version,
    description='Panda package manager and utilities',
    url='https://mesosphere.com',
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
            'pkgpanda=package.cli:main',
        ],
    },
)
