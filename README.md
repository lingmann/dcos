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
