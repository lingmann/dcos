from setuptools import setup, find_packages
from pkgpanda.constants import version

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
            'pkgpanda=pkgpanda.cli:main',
            'mkpanda=pkgpanda.build.cli:main',
        ],
    },
    package_data={
        '': ['*.service', '*.target']
    },
    zip_safe=False
)
