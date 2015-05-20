# DCOS {{ name }} AWS CloudFormation

* For more information on creating a DCOS cluster, see the [Mesosphere beta documentation](http://beta-docs.mesosphere.com/install/eapaws/#create
)</a>.


| Region Name | Region Code | Single Master | HA: Three Master |
| --- | --- | --- | --- |
{% for region in regions %}| {{ region['name'] }} | {{ region['id'] }} | [![Launch stack button](https://s3.amazonaws.com/cloudformation-examples/cloudformation-launch-stack.png)]( https://console.aws.amazon.com/cloudformation/home?region={{ region['id'] }}#/stacks/new?templateURL=https://s3.amazonaws.com/downloads.mesosphere.io/dcos/{{ name }}/single-master.cloudformation.json ) | [![Launch stack button](https://s3.amazonaws.com/cloudformation-examples/cloudformation-launch-stack.png)]( https://console.aws.amazon.com/cloudformation/home?region={{ region['id'] }}#/stacks/new?templateURL=https://s3.amazonaws.com/downloads.mesosphere.io/dcos/{{ name }}/multi-master.cloudformation.json )
{% endfor %}
