SHELL=/bin/bash

.PHONY: aws.templates.stage

aws.templates.stage:
	s3cmd sync unified.json s3://downloads.mesosphere.io/cloudformation/dcos/unified.json
	s3cmd sync simple-unified.json s3://downloads.mesosphere.io/cloudformation/dcos/simple-unified.json

check:
	aws cloudformation validate-template --template-url https://s3.amazonaws.com/downloads.mesosphere.io/cloudformation/dcos/unified.json
	aws cloudformation validate-template --template-url https://s3.amazonaws.com/downloads.mesosphere.io/cloudformation/dcos/simple-unified.json

make_template:
	./gen_aws.py

all: make_template aws.templates.stage check
