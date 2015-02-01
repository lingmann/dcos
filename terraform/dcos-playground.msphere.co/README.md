# dcos0.msphere.co

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

### Test

Show details of currently deployed cluster
```
terraform show
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
