# Bootstrapping the DCOS
TODO(cmaloney): Missing dcos packages: chronos, mesos-cli, web ui

Bootstrap should consist of downloading a tarball, extracting it to the host
filesystem, overlaying a little bit of local config. The local config should
be things like how to find the zookeeper cluster, credentials to provision more
slaves, etc.

Every host must have indicated what "kind" of host it is (master, node)


# Initial bootstrap (Master and slave)

Masters and slaves always download the full bootstrap image for DCOS, and use
that to get to the current cluster state.

```
curl downloads.mesosphere.com/dcos/bootstrap.tar.gz
tar -xzf bootstrap.tar.gz
/opt/mesosphere/bin/pkgpanda --bootstrap {seed_active_file}
```
TODO(cmaloney): Should we report status back to somewhere?

`pkgpanda` will use the seed url to download an initial list of "active"
packages. It will then fetch each of those packages and run a 'pkgpanda activate'.
The activate will

## Master special steps
Masters need to be able to serve all of the packages to new machines as they come up, as well as list the
current cluster configuration.

## Slave special steps
Nothing special should be needed on the slave. It just downloads from one master
the current set of packages (`seed_active_file` = `master.mesos/config/current/slave-active.json`), fetches and then activates the
given packages as specified above.
