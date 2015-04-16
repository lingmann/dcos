# dcos-playground.msphere.co

A Terraform managed test cluster for DCOS. All of the major setup elements are
parameterized so it can be easily used as a starting point for other managed
clusters.

## Quick Start

### Install Terraform

Download Terraform v0.3.6+ and make sure the binary is in your path.

https://terraform.io/downloads.html

### Configure AWS and SSH credentials

```
cp terraform.tfvars.example terraform.tfvars
vim terraform.tfvars
```

### Show

Show details of currently deployed cluster
```
terraform show
```

### Create

If no cluster is currently deployed, then you'll need to re-create it and check
in the new state.

```
./create.sh
# Check in the new cluster state (including discovery_url.tf.json)
git pull && git commit -a
```

### Connect

Connect to the [Mesos](http://master0.dcos-playground.msphere.co:5050) and
[Marathon](http://master0.dcos-playground.msphere.co:8080) web UI **requires
an office or a VPN connection**.

SSH to any of the instances with the username `core` and the
[shared Mesosphere SSH key](https://mesosphere.onelogin.com/notes/13282).

```
ssh -i shared_key core@master0.dcos-playground.msphere.co
ssh -i shared_key core@slave0.dcos-playground.msphere.co
...
```

### Modify

Making changes to currently deployed cluster. **WARNING** This is a shared test
cluster so don't rely on it for your critical work.
```
vim *.tf
terraform plan             # to inspect changes
terraform apply            # to apply changes
git pull && git commit -a  # commit changes (include terraform.tfstate) to repo
```

### Destroy and re-create

This will destroy the current cluster and re-create it from scratch. The
create shell script stores a new Etcd discovery token which is required
whenever a new cluster is created.
```
terraform destroy -force
./create.sh
# Check in the new cluster state (including discovery_url.tf.json)
git pull && git commit -a
```
