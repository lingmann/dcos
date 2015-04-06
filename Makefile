SHELL=/bin/bash

.PHONY: aws.templates.stage

aws.templates.stage:
	s3cmd sync aws/mesos-slave.json s3://downloads.mesosphere.io/cloudformation/dcos/stage-mesos-slave.json
	s3cmd sync aws/mesos-master.json s3://downloads.mesosphere.io/cloudformation/dcos/stage-mesos-master.json
	s3cmd sync aws/mesos.json s3://downloads.mesosphere.io/cloudformation/dcos/stage-mesos.json
	s3cmd sync aws/simple-mesos.json s3://downloads.mesosphere.io/cloudformation/dcos/stage-simple-mesos.json
	s3cmd sync aws/vpc.json s3://downloads.mesosphere.io/cloudformation/dcos/stage-vpc.json

aws.launch.stack:
	s3cmd sync aws/launchstack.html s3://downloads.mesosphere.io/cloudformation/stage-launchstack.html

check:
	aws cloudformation validate-template --template-url https://s3.amazonaws.com/downloads.mesosphere.io/cloudformation/dcos/stage-mesos-slave.json
	aws cloudformation validate-template --template-url https://s3.amazonaws.com/downloads.mesosphere.io/cloudformation/dcos/stage-mesos-master.json
	aws cloudformation validate-template --template-url https://s3.amazonaws.com/downloads.mesosphere.io/cloudformation/dcos/stage-mesos.json
	aws cloudformation validate-template --template-url https://s3.amazonaws.com/downloads.mesosphere.io/cloudformation/dcos/stage-vpc.json
	aws cloudformation validate-template --template-url https://s3.amazonaws.com/downloads.mesosphere.io/cloudformation/dcos/stage-simple-mesos.json

make_template:
	python bin/cloud_config_cf.py --var='$$MASTER_CLOUD_CONFIG' aws/unified.json.template master-cloud-config > /tmp/mcc
	python bin/cloud_config_cf.py --var='$$SLAVE_CLOUD_CONFIG' /tmp/mcc slave-cloud-config > aws/unified.json
