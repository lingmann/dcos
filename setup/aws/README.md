# dcos-cloudformation
One-shot CloudFormation templates for DCOS

## Usage
### Launching with the AWS Web UI

- Go to OneLogin and click on AWS Development:
  https://app.onelogin.com/client/apps. This will authenticate you as a
  temporary admin user in a sandboxed account so production services cannot be
  affected.
- Deploy a cluster using one of the published DCOS templates, for example:
  https://s3.amazonaws.com/downloads.mesosphere.io/dcos/EarlyAccess/aws.html

## Deploying
See the `deploy_aws.py` script at the project root to deploy a new version of
the templates and DCOS image or for more details about how the deploy is
implemented.
