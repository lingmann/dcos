# DCOS Image + Cloud Templates

Tools for building dcos and launching a cluster with it on {AWS,Azure,GCE,Mesos,Vagrant,Terraform}

For documentation see the [dcos-image Wiki pages](https://mesosphere.atlassian.net/wiki/display/DCOS/dcos-image)

Every branch and PR of the repository is automatically built in TeamCity as the project [DCOS Image Builder](https://teamcity.mesosphere.io/project.html?projectId=ClosedSource_Dcos_ImageBuilder&tab=projectOverview).

## Structure

The DCOS Image is made up of two major components. The first is a set of pkgpanda packages (the packages/ folder) of the repository, and the second is a collection of python utilities to generate and deploy specialized templates per Distro/Provider which launch clusters that utilize the packages. The generation code is driven by the 'gen' lib (see `gen/`).

Each provider has it's own top-level utility script which contains helpers for doing various deployment, updating, testing actions for that provider.

## Launching a cluster for development (Vagrant, AWS)

See: https://mesosphere.atlassian.net/wiki/display/DCOS/Development+Clusters

## Integrating your component:

 - [Custom Builds](https://mesosphere.atlassian.net/wiki/display/DCOS/Custom+DCOS+Builds) for testing
 - [Pull Requests](https://mesosphere.atlassian.net/wiki/display/DCOS/Pull+Requests) to land your changes
 - [Making Changes](https://mesosphere.atlassian.net/wiki/display/DCOS/Making+Changes) guidance on what will / won't land.

 If you have questions, please ask #dcos in slack, make a meeting, or come say hi.

## Building locally

Doesn't work on OSX, requires Linux. In general it is HIGHLY recommended to just let TeamCity do the build for you.

The instructions below are infrequently updated and likely out of date whereas TeamCity is kept always building.

## Getting Started

General requirements: Python3, pkgpanda, everything in requirements.txt, docker relatively new (1.5+ probably)

Building dcos-image.

1) Setup a Python3 virtualenv containing pkgpanda, dcos-image dependencies.
```
# Make a virtualenv (python 3.4 method). Others work as well. Must be python3
pyvenv pkgpanda_env
source pkgpanda_env/bin/activate
# cd into pkgpanda checkout
# NOTE: Develop makes it so local changes will be reflected automatically
python3 setup.py develop

# cd into dcos-image checkout
# Install dcos-image requirements
pip install -r requirements.txt
```
2) Build packages
```
# cd dcos-image checkout
cd packages
mkpanda tree
```

3) Build a custom aws with your local changes
```
# cd dcos-image checkout
./aws.py build --upload
```

## Deploying / Working across all providers

TODO(cmaloney): Document how to do meta-work for all providers/platforms (Make a release for all providers)

## Info for various providers

### AWS

The AWS tooling makes heavy use of boto3. It requires that you setup two [profiles](http://boto3.readthedocs.org/en/latest/guide/configuration.html#configuration-files), "development" and "production" which have credentials for the respective AWS Account buttons in OneLogin.

- `aws.py build`: Make a new build of dcos_image and the current templates. Optionally upload the build so that a test cluster can be launched with it.
- `aws.py make_candidate`: Make a new candidate for a release. Performs a build, then generates the single-master, multi-master, and button page templates. Uploads them all to a testing bucket for internal testing.

TODO(cmaloney): More AWS commands

### Vagrant multi node cluster
`test/run-all name platform [platform...]` build the necessary artifacts and spins up a multi node cluster (3 dedicated masters, 2 slaves) for the given platform (bash, chef etc).

You can also test local changes by running `PLATFORM=platform vagrant up` in `test`/ after creating the build artifacts manually.
