# dcos-cloudformation
One-shot CloudFormation templates for DCOS

# Usage
```
aws cloudformation create-stack --stack-name dcos --template-url=https://s3.amazonaws.com/downloads.mesosphere.io/cloudformation/dcos/stage-mesos.json --capabilities CAPABILITY_IAM --parameters $(cat parameters) --region us-west-2
```
