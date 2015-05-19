Notes on common values
======================

:Author: Marco Massenzio (marco@mesosphere.io)
:Date: 2015-04-29
:Revision: 0.1
:Status: Draft


Overview
--------

Wherever possible, properties and user-input should be common across cloud providers; this is the
current list for AWS we should separate out the ones that are specific on a per-provider basis:


    ``AdminLocation``
        The IP range to whitelist for admin access.

    ``MasterInstanceType``
        The instance type for the Master VMs - actual values to be provider-specific (and,
        most likely only available for the user to pick from a restricted list)

    ``SlaveInstanceType``
        Same as ``MasterInstanceType`` but for the Worker nodes

    ``MasterInstanceCount``, ``SlaveInstanceCount``
        Number of master/slave nodes to instantiate (integer values)

    ``MasterQuorumCount``
        Number of masters needed for Mesos replicated log registry quorum 
        (should be ``ceiling(<MasterInstanceCount>/2)``)

    ``BootstrapRepoRoot``
        Root repository for bootstrapping (must not end in /)

    ``StackCreationTimeout``
        Timeout on initial stack creation (TODO: in seconds? minutes? centuries?)

Other variables that need to be 'injected' into the templates (or could be hard-coded)


    ``url_bootstrap``
        http://s3.amazonaws.com/downloads.mesosphere.io/dcos/EarlyAccess/
        (to be hard-coded for now)



AWS Template
------------

These are the details for the AWS templates properties::


    {
          "AdminLocation" : {
                "Description" : "The IP range to whitelist for admin access.",
                "Type" : "String",
                "MinLength" : "9",
                "MaxLength" : "18",
                "Default" : "0.0.0.0/0",
                "AllowedPattern" : "^([0-9]+\\.){3}[0-9]+\\/[0-9]+$",
                "ConstraintDescription" : "must be a valid CIDR."
          },
          "MasterInstanceType" : {
                "Description" : "EC2 instance type",
                "Type" : "String",
                "Default" : "r3.large",
                "AllowedValues" : [ "t1.micro","t2.micro","t2.small","t2.medium","m1.small","m1.medium","m1.large","m1.xlarge","m2.xlarge","m2.2xlarge","m2.4xlarge","m3.medium","m3.large","m3.xlarge","m3.2xlarge","c1.medium","c1.xlarge","cc1.4xlarge","cc2.8xlarge","cg1.4xlarge","r3.large","r3.xlarge","r3.2xlarge","r3.4xlarge","r3.8xlarge"],
                "ConstraintDescription" : "must be a valid EC2 instance type."
          },
          "SlaveInstanceType" : {
                "Description" : "EC2 instance type",
                "Type" : "String",
                "Default" : "r3.large",
                "AllowedValues" : [ "t1.micro","t2.micro","t2.small","t2.medium","m1.small","m1.medium","m1.large","m1.xlarge","m2.xlarge","m2.2xlarge","m2.4xlarge","m3.medium","m3.large","m3.xlarge","m3.2xlarge","c1.medium","c1.xlarge","cc1.4xlarge","cc2.8xlarge","cg1.4xlarge","r3.large","r3.xlarge","r3.2xlarge","r3.4xlarge","r3.8xlarge"],
                "ConstraintDescription" : "must be a valid EC2 instance type."
          },
          "MasterInstanceCount" : {
                "Description" : "Number of master nodes to launch",
                "Type" : "Number",
                "Default" : "1"
          },
          "SlaveInstanceCount" : {
                "Description" : "Number of slave nodes to launch",
                "Type" : "Number",
                "Default" : "5"
          },
          "MasterQuorumCount" : {
                "Description" : "Number of masters needed for Mesos replicated log registry quorum (should be ceiling(<MasterInstanceCount>/2))",
                "Type" : "Number",
                "Default" : "1"
          },
          "BootstrapRepoRoot" : {
                "Description" : "Root repository for bootstrapping (must not end in /)",
                "Type" : "String",
                "Default" : ""
          },
          "StackCreationTimeout" : {
                "Description" : "Timeout on initial stack creation",
                "Type" : "String",
                "Default": "PT30M"
          }
    }
