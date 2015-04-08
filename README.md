# dcos-cloudformation
One-shot CloudFormation templates for DCOS

# Usage
### Launching with the AWS Web UI
1. Go to OneLogin and click on AWS Development: https://app.onelogin.com/client/apps. This will create a temporary admin user for you in a sandboxed account so production services cannot be affected.
1. Click this button:
[![Launch stack button](https://s3.amazonaws.com/cloudformation-examples/cloudformation-launch-stack.png)](https://console.aws.amazon.com/cloudformation/home?region=us-west-2#/stacks/new?templateURL=https://s3.amazonaws.com/downloads.mesosphere.io/cloudformation/dcos/stage-simple-unified.json)
1. Alternatively, if you want to set your own parameters:
[![Launch stack button](https://s3.amazonaws.com/cloudformation-examples/cloudformation-launch-stack.png)](https://console.aws.amazon.com/cloudformation/home?region=us-west-2#/stacks/new?templateURL=https://s3.amazonaws.com/downloads.mesosphere.io/cloudformation/dcos/stage-mesos.json)
1. Follow the wizard (please report any parameters you find confusing!). There are two fields you must set:
  1. *Name* - give your CloudFormation stack a recognizable name, and
  1. *KeyName* - use the existing `dcos-ea` key if you don't have one defined.
1. Make sure to check the 'I agree to IAM capabilities' checkbox at the end.

#### Creating a keypair
To create a key pair to use when SSHing to instances, navigate to the EC2 console (making sure you're in the correct region), select the `Key Pairs` element from the left-hand pane. Then hit the `Create Key Pair` button near the top-left of the middle pane.

#### Accessing the cluster
1. On the AWS CloudFormation UI, click on the corresponding MesosMaster stack for your cluster and select the *Output* tab. ![Image of CF UI](https://www.dropbox.com/s/ylj9z92n4zvm3ri/Screenshot%202015-03-31%2015.03.41.png?dl=1)
2. The DNS address field will give you the DNS name for the external load balancer in front of the Mesos masters. You can access the DCOS here:

| Service | Address |
| --- | --- |
| DCOS Web UI | *EXTERNAL_ELB_DNS* |
| Mesos Web UI | *EXTERNAL_ELB_DNS*:5050 |
| Marathon Web UI | *EXTERNAL_ELB_DNS*:8080 |

#### SSH access
To SSH to individual instances of your cluster you will have to switch the to EC2 UI and filter to find the master and slaves nodes of your cluster.
```
ssh -i <key.pem> core@<node_hostname>
```

#### VPN access
One easy way to set up VPN access is with the [pfSense VPN AWS appliance](https://aws.amazon.com/marketplace/pp/B00G6P8CVW/ref=srh_res_product_title?ie=UTF8&sr=0-2&qid=1385067602051).


To launch it, simply click on "Continue" and then "Launch with EC2
Console" and be sure to put it in the VPC and select "Assign Public IP
address".

OpenVPN comes preconfigured; you just need to download the
configuration from the web console, linked above. If you'd like to
learn more, here is the [user guide](http://www.netgate.com/doc/AWS-VPN-appliance/user_guide.html).

This VPN appliance costs about 100 USD a month -- 50 for the
"software" and 50 for the instance (it only runs on bigger instances).

#### Resizing the cluster
Currently you can change the number of slaves, but not the number of masters.
To change the number of slaves:
1. Go to the CloudFormation UI
2. Select the umbrella CF stack (the name of your cluster with no suffix)
3. Hit the *Update Stack* button
4. Follow the wizard, changing the SlaveInstantCount parameter

### Launching with AWS CLI
```
aws cloudformation create-stack --stack-name dcos --template-url=https://s3.amazonaws.com/downloads.mesosphere.io/cloudformation/dcos/stage-mesos.json --capabilities CAPABILITY_IAM --parameters $(cat parameters) --region us-west-2
```

# Networking
The cluster runs inside a VPC with an Internet gateway. All traffic is allowed between the VPC and a specified CIDR (by default 0.0.0.0/0). DNS names of instances resolve to internal IPs inside when resolved from inside the VPC, and to external IPs when resolved from outside the VPC. Therefore, if slaves register with their EC2 hostname, then services which require connecting directly to slaves like the slave sandbox will just work.

### Exposing ports on the external load balancer
To expose ports on the ELB (for example, to access new frameworks' REST APIs), just navigate to the EC2 console, select the `Load Balancers` element on the left-hand pane under `Network & Security`. Find your load balancer, making sure to select the external one, select the `Listener` tab and click `Edit` adding the appropriate port forwarding rules.

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

# Quota
AWS accounts must have sufficent remaining quota to launch the CloudFormation template. Our one-shot template consumes:

| Resource | Quantity |
| --- | --- |
| VPC | 1 |
| CloudFormation stacks | 4 |
| ELB | 2 |
| Auto Scaling groups | 2 |
| EC2 Instances | 5 |

To request a quota increase, navigate to the Support Center console and create a case requesting the appropriate resources. Response times are generally pretty quick.


# Decommissioning
Unfortunately there isn't an elegant way to decommission clusters provisioned in this manner. This is because non-empty S3 buckets cannot be deleted automatically. The solution is trivial but inconvenient and requires running a script that deletes the contents of the S3 bucket, deletes the S3 bucket, and finally deletes the umbrella CloudFormation stack. This script requires credentials for an IAM user with very high access.

### Manually deleting S3 buckets
To delete an S3 bucket, you must first delete its contents. To do so from the AWS web UI, navigate to the S3 console, select the bucket for your cluster, select and delete all of its items (under the `Actions` drop down). Finally, you must navigate to the previous screen and delete the bucket (before it gets repopulated by Exhibitor). After the bucket has been deleted, you can simply hit `Delete Stack` on your CloudFormation stack.

# Customization
### Launching in a different region
To launch in a different region it should be sufficient to:
1. Change the region on the CF web UI (button near top right)
2. Update the CoreOS AMI to correspond with the region (https://coreos.com/docs/running-coreos/cloud-providers/ec2/)

### Launching in multi-master mode (HA)
1. Update the *MasterInstanceCount* parameter (recommended odd number)
2. Update the *MasterQuourumCount* parameter (recommended ceil(MasterInstanceCount*/2)

# Known Issues

# Software
| Component | Details |
| --- | --- |
| OS | CoreOS Beta Channel 633.1.0 for HVM |
| Pkgpanda | |
| Mesos DNS | |
| DCOS CLI | |
