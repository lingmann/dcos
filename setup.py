#!/usr/bin/env python3
import os

import setuptools
from setuptools import find_packages, setup


DOCKERFILE_TEMPLATE = '''
FROM python:3.4.3-slim
MAINTAINER support+dcos@mesosphere.io

RUN apt-get update && \
  apt-get install -y \
    curl \
    pxz \
    openssh-client \
    openssh-server \
    git \
    gcc && \
  rm -rf /var/lib/apt/lists/* && apt-get clean

COPY . /dcos-installer

WORKDIR /dcos-installer

RUN pip install --find-links=ext dcos_image pkgpanda
RUN pip install .

ENV DCOS_IMAGE_COMMIT={DCOS_IMAGE_COMMIT}
ENV CHANNEL_NAME={CHANNEL_NAME}
ENV BOOTSTRAP_ID={BOOTSTRAP_ID}
'''

SCRIPT_TEMPLATE = '''
#!/bin/bash
set -o errexit -o nounset -o pipefail

PRG=$0
usage()
{{
    echo "Usage: $PRG [options] [CMD...]"
    echo "Any arguments provided will be interpretted as commands for the installer docker container"
    echo "Options:"
    echo "--help      Print this statement"
    echo "--version   Print git SHA's for repos used"
    exit 0
}}

version()
{{
    echo "dcos-installer revision: {DCOS_INSTALLER_COMMIT}"
    echo "dcos-image revision: {DCOS_IMAGE_COMMIT}"
    exit 0
}}

if [ -z "$@$" ]; then
    first_arg="$1"
    case "$first_arg" in
        --help) usage ;;
        --version) version ;;
    esac
fi

# preflight checks
docker version >/dev/null 2>&1 || {{ echo >&2 "docker should be installed and running. Aborting."; exit 1; }}

# extract payload and load into docker if not extracted
set +o errexit
docker inspect {docker_image_name} &> /dev/null
docker_ret=$?
set -o errexit
if [ "$docker_ret" -eq "1" ]; then
  echo Extracting docker container from this script
  sed '0,/^#EOF#$/d' $0 | docker load
fi

if [ ! -d installer_data ]; then
    mkdir installer_data
fi

if [ -z "$@" ]; then
docker run -i -v $(pwd)/installer_data/:/genconf {docker_image_name} dcos_installer --web
else
docker run -i -v $(pwd)/installer_data/:/genconf {docker_image_name} "$@"
fi

exit 0'''


class BuildDocker(setuptools.Command):
    description = 'Build a docker run environment and package in a BASH script'
    user_options = []

    def initialize_options(self):
        self.dcos_installer_commit = None
        self.dcos_image_commit = None
        self.channel_name = None
        self.bootstrap_id = None

    def finalize_options(self):
        self.dcos_installer_commit = os.getenv("DCOS_INSTALLER_COMMIT", None)
        self.dcos_image_commit = os.getenv("DCOS_IMAGE_COMMIT", None)
        self.channel_name = os.getenv("CHANNEL_NAME", 'deadbeef')
        self.bootstrap_id = os.getenv("BOOTSTRAP_ID", 'deadbeef')

    def run(self):
        # Write Dockerfile
        dockerfile_contents = DOCKERFILE_TEMPLATE.format(
            DCOS_IMAGE_COMMIT=self.dcos_image_commit,
            CHANNEL_NAME=self.channel_name,
            BOOTSTRAP_ID=self.bootstrap_id)
        with open('Dockerfile', 'w') as dockerfile_fh:
            dockerfile_fh.write(dockerfile_contents)
        # Build docker image
        # Import docker here so that setup can be run without installing docker_py
        import docker
        docker_client = docker.Client(base_url='unix://var/run/docker.sock', version='auto')
        docker_image_name = "dcos_installer:{}".format(self.dcos_installer_commit)
        build_results = docker_client.build(
                path=os.getcwd(),
                tag=docker_image_name,
                rm=True,
                decode=True)
        for line in build_results:
            try:
                print(line['stream'])
            except KeyError:
                try:
                    error = line['error']
                    exit(error)
                except KeyError:
                    for k in line.keys():
                        print(line[k])
        docker_image = docker_client.get_image(docker_image_name)
        # Write script to file
        installer_filename = "dcos_installer.sh"
        with open(installer_filename, 'w') as installer_fh:
            installer_fh.write(SCRIPT_TEMPLATE.format(
                docker_image_name=docker_image_name,
                DCOS_INSTALLER_COMMIT=self.dcos_installer_commit,
                DCOS_IMAGE_COMMIT=self.dcos_image_commit
                ) + '\n#EOF#\n')
        # Export docker image to script
        with open(installer_filename, 'ab') as installer_fh:
            tar_stream = docker_image.stream()
            for chunk in tar_stream:
                installer_fh.write(chunk)
        os.chmod(installer_filename, 0o775)

setup(
    name='dcos_installer',
    description='The DCOS Installer',
    version='0.1',
    author='Mesosphere, Inc.',
    author_email='support@mesosphere.io',
    cmdclass={
        'build_docker': BuildDocker},
    packages=['dcos_installer'] + find_packages(),
    install_requires=[
        'asyncio',
        'aiohttp',
        'aiohttp_jinja2',
        'docker_py',
        'pytest',
        'pytest-mock',
        'tox',
        'webtest',
        'webtest_aiohttp'],
    entry_points={
        'console_scripts': ['dcos_installer = dcos_installer.entrypoint:main']
        },
    package_data={'dcos_installer': ['templates/*/*']},
    zip_safe=False
    )
