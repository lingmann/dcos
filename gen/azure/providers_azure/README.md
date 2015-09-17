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

## Microsoft Contacts

* Primary: Ross.Gardler@microsoft.com
* Secondary: mahesh.thiagarajan@microsoft.com, kasing@microsoft.com

## Schema and apiVersions

The recommendation from Microsoft as of 2015-09-17 is to develop ARM templates
with the following versions:

* Schema: http://schema.management.azure.com/schemas/2015-01-01/deploymentTemplate.json#
* apiVersions (all but Storage): 2015-06-15
* Storage apiVersions: 2015-05-01-preview

## TODO

* Validate uniquename input, must be between 3-24 char in length and use numbers
  and lower-case letters only.
