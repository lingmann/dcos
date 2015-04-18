## Quick Start

- Update all instances of `REPLACEME` in `azuredeploy-parameters.json` with a
  globally unique UUID in the Azure namespace (must be between 3-24 characters
  and use numbers and lower-case letters only). Something like `mspherejtl`
  would likely work (msphere + your initials).

- Stack must be created in the "West US" region

- Create the stack

  ```
  # Create the stack, using your globally unique UUID
  ./create.sh REPLACEME
  ```

- SSH to stack. You will need the [Mesosphere shared SSH key]
  (https://mesosphere.onelogin.com/notes/13282).

  ```
  ssh core@master0-REPLACEME.westus.cloudapp.azure.com
  ```

- Delete the stack

  ```
  # Delete the stack, using your globally unique UUID
  ./delete.sh REPLACEME
  ```

## Cloud Config

The `slaveCustomData` and `masterCustomData` in the `azuredeploy.json` template
was generated with `gen_azure_custom_data.py`. For example:

  ```
  ./gen_azure_custom_data.py azure-master.yaml
  ./gen_azure_custom_data.py azure-slave.yaml
  ```

## Azure Resource Manager Template Language (ARM)

Template language reference:
https://msdn.microsoft.com/en-us/library/azure/dn835138.aspx

## Azure Web Portal

Special link to see portal with data from the new resource API:

https://ms.portal.azure.com/?Microsoft_Azure_Compute=true&Microsoft_Azure_Storage=true&Microsoft_Azure_Network=true#blade/HubsExtension/BrowseResourceGroupBlade/resourceType/Microsoft.Resources%2Fsubscriptions%2FresourceGroups?journeyId=5D94E383-E5A4-4DC4-A736-419A062A1175

## Azure Resource Browser

https://resources.azure.com
