# DCOS Image + Cloud Templates

Tools for building dcos and launching a cluster with it on {AWS,Azure,GCE,Mesos,Vagrant,Terraform}

The core of DCOS is built automated in TeamCity and pushed to S3. See the TeamCity
[DCOS Image Builder](https://teamcity.mesosphere.io/project.html?projectId=ClosedSource_Dcos_ImageBuilder&tab=projectOverview)
project.

Every branch of `dcos-image` is automatically built by TeamCity, to make a new
release candidate simply create a new branch in the `dcos-image` repository.

## Structure

The DCOS Image is made up of two major components. The first is a set of pkgpanda packages (the packages/ folder) of the repository, and the second is a collection of python utilities to generate and deploy specialized templates per Distro/Provider which launch clusters that utilize the packages. The generation code is driven by the 'gen' lib (see `gen/`).

Each provider has it's own top-level utility script which contains helpers for doing various deployment, updating, testing actions for that provider.

## Getting Started

General requirements: Python3, pkgpanda, everything in requirements.txt, docker relatively new (1.5+ probably)

Building dcos-image.

1) Setup a Python3 virtualenv containing pkgpanda, dcos-image dependencies.
```
# Make a virtualenv (python 3.4 method). Others work as well. Must be python3
pyvenv pkgpanda_env
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

### Vagrant (TODO)

`vagrant.py`: Performs a DCOS build and generates a self-contained script to create a Vagrantfile to launch a DCOS cluster.

Uploads all the packages, bootstrap, config package automatically, as well as the script to generate the Vagrantfile.

To use simply download the script from the provided url, run the script, then run `vagrant up`.
