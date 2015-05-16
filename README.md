# DCOS Image + Cloud Templates

Tools for building dcos and launching a cluster with it on {AWS,Azure,GCE,Mesos,Vagrant,Terraform}

## Structure
Lots currently shifting around. Main places to look

 - *packages/* All the packages that make up the base DCOS shipping image.
 - *providers/* Files for launching DCOS on various providers (AWS, Azure, GCE, Mesos, Vagrant etc.)

Soon there will be a script for compiling provider-specific templates from
generic general-purpose ones.

The core of DCOS is built automated in TeamCity and pushed to S3. See the TeamCity
[DCOS Image Builder](https://teamcity.mesosphere.io/project.html?projectId=ClosedSource_Dcos_ImageBuilder&tab=projectOverview)
project.

# Making a Test Build / Release Candidate

Every branch of `dcos-image` is automatically built by TeamCity, to make a new
release candidate simply create a new branch in the `dcos-image` repository.

If the commit has been built by TeamCity before you'll need to manually press the
run button in TeamCity to get it to do a build.

Once there is a build, use the `AWS CloudFormation` tab in TeamCity to launch
clusters / test. The release name is 'testing/{branch-name}' for use in scripts
 / automated cluster launchers.

Additional pushes to the branch will update the bootstrap tarball and packages.
The buttons always point to the latest build of the branch, regardless of what
build the page was built with.

# Hand-testing

Just run the 'deploy_aws' script giving it a unique name prefixed with your name.
It will output a link to all the magic buttons for you.

# Deploying a "testing" / release candidate  new Image

`./promote_aws <testing_name> <release_name>`

For promoting EA4 to EarlyAccess this would be:

`./promote_aws EA4 EarlyAccess`

Note that the script generates the landing page buttons at the time when it is
run. The CloudFormation, active.json, bootstrap.tar.xz and packages are all
grabbed / copied directly from the old s3 location to the new. Only the packages
in the active.json of the testing name are copied, other / older versions of
packages sitting around are ignored.
