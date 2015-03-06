SHELL=/bin/bash

.PHONY: aws.templates.stage

aws.templates.stage:
	s3cmd sync aws/mesos-slave.json s3://downloads.mesosphere.io/cloudformation/dcos/stage-mesos-slave.json
	s3cmd sync aws/mesos-master.json s3://downloads.mesosphere.io/cloudformation/dcos/stage-mesos-master.json
	s3cmd sync aws/mesos.json s3://downloads.mesosphere.io/cloudformation/dcos/stage-mesos.json
	s3cmd sync aws/vpc.json s3://downloads.mesosphere.io/cloudformation/dcos/stage-vpc.json

aws.launch.stack:
	s3cmd sync aws/launchstack.html s3://downloads.mesosphere.io/cloudformation/stage-launchstack.html
