# Usage Documentation

## CoreOS cloud-config documentation

https://github.com/coreos/coreos-cloudinit/blob/master/Documentation/cloud-config.md

## Retrieving fleet logs

Fetch journal entries for containers started with fleet:
```
fleetctl journal ...
```

## Verify cloud-init user data on an EC2 instance

[EC2 Metadata and User Data documentation](http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-metadata.html)
```
curl http://169.254.169.254/latest/user-data
```

## Test cloud config user data stored in a local file
```
coreos-cloudinit --from-file /tmp/user-data.yml
```

## Execute arbitrary bash code/variable subst in systemd units

https://gist.github.com/nickjacob/9909574

## CoreOS runtime configuration changes

https://github.com/coreos/etcd/blob/master/Documentation/runtime-configuration.md

## Using SRV records for cluster discovery

https://github.com/coreos/etcd/blob/master/Documentation/clustering.md#dns-discovery

## Installing to disk

https://github.com/coreos/init/blob/master/bin/coreos-install

## Booting via iPXE

https://coreos.com/docs/running-coreos/bare-metal/booting-with-ipxe/#setting-up-the-boot-script

## Automatically validate cloud-config

We should be able to use [CoreOS validator](https://coreos.com/validate/) or
`coreos-cloudinit -validate`
