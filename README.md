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

## Deploying / Working across all providers

TODO(cmaloney): Document how to do meta-work for all providers/platforms (Make a release for all providers)

## Info for various providers

### AWS

Configuring AWS:
You need to add two profiles to your AWS/botocore config. "development" and "production". "production" needs to point to have credentials poitning to the "AWS Production" in OneLogin. "development" to "AWS Development" in OneLogin.

- `aws.py build`: Make a new build of dcos_image and the current templates. Optionally upload the build so that a test cluster can be launched with it.
- `aws.py make_candidate`: Make a new candidate for a release. Performs a build, then generates the single-master, multi-master, and button page templates. Uploads them all to a testing bucket for internal testing.

TODO(cmaloney): More AWS commands

### Vagrant (TODO)

