# {{ name }} AWS CloudFormation

* [Go to OneLogin and click on AWS Development](https://app.onelogin.com/client/apps)
* Descriptions of the cluster types are below.
* Follow the DCOS Documentation on exploring / navigating the cluster.
* Don't use the TestCluster button.

| Region | Single-Master | Multi-Master | Custom | TestCluster |
| --- | --- | --- | --- | --- |
{% for region in regions %}| {{ region }} | [![Launch stack button](https://s3.amazonaws.com/cloudformation-examples/cloudformation-launch-stack.png)]( https://console.aws.amazon.com/cloudformation/home?region={{ region }}#/stacks/new?templateURL=https://s3.amazonaws.com/downloads.mesosphere.io/dcos/{{ name }}/single-master.cloudformation.json ) | [![Launch stack button](https://s3.amazonaws.com/cloudformation-examples/cloudformation-launch-stack.png)]( https://console.aws.amazon.com/cloudformation/home?region={{ region }}#/stacks/new?templateURL=https://s3.amazonaws.com/downloads.mesosphere.io/dcos/{{ name }}/multi-master.cloudformation.json ) | [![Launch stack button](https://s3.amazonaws.com/cloudformation-examples/cloudformation-launch-stack.png)]( https://console.aws.amazon.com/cloudformation/home?region={{ region }}#/stacks/new?templateURL=https://s3.amazonaws.com/downloads.mesosphere.io/dcos/{{ name }}/cloudformation.json ) | [![Launch stack button](https://s3.amazonaws.com/cloudformation-examples/cloudformation-launch-stack.png)]( https://console.aws.amazon.com/cloudformation/home?region={{ region }}#/stacks/new?templateURL=https://s3.amazonaws.com/downloads.mesosphere.io/dcos/{{ name }}/testcluster.cloudformation.json )
{% endfor %}

## Cluster Types

### Single-Master

Spawns a cluster with 1 master and 5 slaves. Should be suitable for running basic tests.

### Multi-Master

Spawns a cluster with 3 masters and 5 slaves. HA. Capable of basic production workloads, as well as testing how frameworks interact with master-failover.

### Custom

Allows launching arbitrary cluster sizes / configurations. Choose how many masters, slaves, what instance types, etc.

*NOTE*: It is critical to correctly set the quorum size in relation to the number of masters. If it is incorrect, your cluster will fail to startup properly (Usually lots and lots of replicated log messages never getting anywhere).

### TestCluster

Cluster with DataDog installed, as well as a second disk mounted at '/ephemeral'. This will be used to setup the [Testing Infrastructure](https://docs.google.com/a/mesosphere.io/document/d/1oif3TXJf2hyvD8XQKwfW95OY7apj7H7RdkEwSpHGKbI/edit?usp=sharing).
