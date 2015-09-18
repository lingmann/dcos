## Quick Start

- Create the stack

  ```
  # Create the stack, MY_STACK_ID must be 3-24 chars and consist of numbers and
  # lower case letters only.
  ./create.sh $MY_STACK_ID $NUM_SLAVES
  ```

- SSH to stack. You will need the [Mesosphere shared SSH key]
  (https://mesosphere.onelogin.com/notes/13282).

  ```
  ssh core@master0-${MY_STACK_ID}.westus.cloudapp.azure.com
  ```

- Delete the stack

  ```
  # Delete the stack, using your globally unique UUID
  ./delete.sh $MY_STACK_ID
  ```

## Cloud Config

The `slaveCustomData` and `masterCustomData` in the `azuredeploy.json` template
was generated with `gen_azure_custom_data.py`. For example:

  ```
  ./gen_azure_custom_data.py azure-master.yaml
  ./gen_azure_custom_data.py azure-slave.yaml
  ```

## Azure Resource Browser

https://resources.azure.com/

## Azure Resource Manager (ARM) Reference Material

* [Authoring ARM Templates](https://azure.microsoft.com/en-us/documentation/articles/resource-group-authoring-templates/)
* [ARM Template Functions](https://azure.microsoft.com/en-us/documentation/articles/resource-group-template-functions/)
* [ARM Schema Definitions](https://github.com/Azure/azure-resource-manager-schemas/tree/master/schemas)
* [Examples](https://github.com/azure/azure-quickstart-templates)

## Microsoft Contacts

* Primary: Ross.Gardler@microsoft.com
* Secondary: mahesh.thiagarajan@microsoft.com, kasing@microsoft.com

## Schema and apiVersions

The recommendation from Microsoft as of 2015-09-17 is to develop ARM templates
with the following versions:

* Schema: http://schema.management.azure.com/schemas/2015-01-01/deploymentTemplate.json#
* apiVersions (all but Storage): 2015-06-15
* Storage apiVersions: 2015-05-01-preview

## Virtual Machine Scale Sets

virtualMachineScaleSets is a new feature that Microsoft is developing similar
to autoscale groups. It is not generally available yet but will be made
available to an early access group on Oct. 1. There is an example of how this
will work in Ross' [azure-myriad](https://github.com/gbowerman/azure-myriad/)
and
[mesos-swarm-marathon](https://github.com/gbowerman/azure-quickstart-templates/tree/master/mesos-swarm-marathon)
examples.

## TODO

* Validate uniquename input, must be between 3-24 char in length and use numbers
  and lower-case letters only.
* Support or protect against single-quote characters in cloud config templates.
  Currently, a single quote character will break the ARM template when injected.
  The only approach that seems possible at this point (without some additional
  help from Microsoft) is referencing a single quote character with an ARM
  template variable, i.e. variables('singleQuote').
