# {{ name }} AWS CloudFormation

* [Go to OneLogin and click on AWS Development](https://app.onelogin.com/client/apps)
* Click one of the buttons below. Simple has less parameters, Normal lets you tweak things.
* Follow the DCOS Documentation on exploring / navigating the cluster.

| Region | Single-Master | Multi-Master | Custom |
| --- | --- | --- | --- |
{% for region in regions %}| {{ region }} | [![Launch stack button](https://s3.amazonaws.com/cloudformation-examples/cloudformation-launch-stack.png)]( https://console.aws.amazon.com/cloudformation/home?region={{ region }}#/stacks/new?templateURL=https://s3.amazonaws.com/downloads.mesosphere.io/dcos/{{ name }}/single-master.cloudformation.json ) | [![Launch stack button](https://s3.amazonaws.com/cloudformation-examples/cloudformation-launch-stack.png)]( https://console.aws.amazon.com/cloudformation/home?region={{ region }}#/stacks/new?templateURL=https://s3.amazonaws.com/downloads.mesosphere.io/dcos/{{ name }}/multi-master.cloudformation.json ) | [![Launch stack button](https://s3.amazonaws.com/cloudformation-examples/cloudformation-launch-stack.png)]( https://console.aws.amazon.com/cloudformation/home?region={{ region }}#/stacks/new?templateURL=https://s3.amazonaws.com/downloads.mesosphere.io/dcos/{{ name }}/cloudformation.json )
{% endfor %}
