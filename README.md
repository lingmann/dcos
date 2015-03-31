# dcos-cloudformation
One-shot CloudFormation templates for DCOS

# Usage
### AWS Web UI
1. Go to OneLogin and click on AWS Development: https://app.onelogin.com/client/apps. This will create a temporary admin user for you in a sandboxed account so production services cannot be affected.

2. Click the button [here](http://downloads.mesosphere.io/cloudformation/stage-launchstack.html).

3. Follow the wizard (please report any parameters you find confusing!).
4. There are two fields you must set: *Name* (name of the CloudFormation stack) and *KeyName* (name of the SSH key to use).
4. Make sure to check the IAM capabilities checkbox.


### CLI
```
aws cloudformation create-stack --stack-name dcos --template-url=https://s3.amazonaws.com/downloads.mesosphere.io/cloudformation/dcos/stage-mesos.json --capabilities CAPABILITY_IAM --parameters $(cat parameters) --region us-west-2
```

# Networking
The cluster runs inside a VPC with an Internet gateway. All traffic is allowed between the VPC and a specified CIDR (by default 0.0.0.0/0). DNS names of instances resolve to internal IPs inside when resolved from inside the VPC, and to external IPs when resolved from outside the VPC. Therefore, if slaves register with their EC2 hostname, then services which require connecting directly to slaves like the slave sandbox will just work.

# Zookeeper/Exhibitor
Zookeeper and Exhibitor run colocated to the masters. Exhibitor is a supervisor process for Zookeeper that manages bootstrapping, back-ups, and resizing of ZK clusters. Exhibitor uses an S3 bucket to sync configs among different ZK nodes. We wait until all ZK nodes show up in Exhibitor with exactly one leading master.

Useful Exhibitor endpoints:

```
masterELB:8181/exhibitor/v1/ui/index.html
```
```
masterELB:8181/exhibitor/v1/cluster/status
```

# Security best practices
We recommend running this CloudFormation template inside a sub-account to guarantee isolation. As part of the template, we create an IAM user with access to S3 for Exhibitor. Furthermore, decommissioning requires an IAM user with the ability to delete CloudFormation stacks, IAM users, and S3 buckets. 

# Decommissioning
Unfortunately there isn't an elegant way to decommission clusters provisioned in this manner. This is because non-empty S3 buckets cannot be deleted automatically. The solution is trivial but inconvenient and requires running a script that deletes the contents of the S3 bucket, deletes the S3 bucket, and finally deletes the umbrella CloudFormation stack. This script requires credentials for an IAM user with very high access.

# Software
| Component | Details |
| --- | --- |
| OS | CoreOS Alpha Channel 618 |
| Pkgpanda | |
| Mesos DNS | |
| DCOS CLI | |

