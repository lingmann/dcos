SHELL=/bin/bash

.PHONY: aws.templates.stage

aws.templates.stage:
	s3cmd sync aws/unified.json s3://downloads.mesosphere.io/cloudformation/dcos/ea-unified.json

aws.launch.stack:
	s3cmd sync aws/launchstack.html s3://downloads.mesosphere.io/cloudformation/stage-launchstack.html

check:
	aws cloudformation validate-template --template-url https://s3.amazonaws.com/downloads.mesosphere.io/cloudformation/dcos/ea-unified.json

make_template:
	python bin/cloud_config_cf.py --var='$$MASTER_CLOUD_CONFIG' aws/unified.json.template master-cloud-config > /tmp/mcc
	python bin/cloud_config_cf.py --var='$$SLAVE_CLOUD_CONFIG' /tmp/mcc slave-cloud-config > aws/unified.json
